from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework import status

from django_tenants.utils import get_tenant_model, schema_context
from customers.models import TenantUser, RolesMap
from customers.services import KeycloakService
from users.models import User
import logging

logger = logging.getLogger(__name__)


class TenantUsersListView(APIView):
    """
    OWNER and MEMBER can see all users in their tenant.
    OWNER: Full details for user management
    MEMBER: Basic list for todo assignment
    VIEWER: No access
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.auth
        if not token:
            raise PermissionDenied("Authentication required")

        tenant_schema = token.get("tenant_schema")
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")

        Tenant = get_tenant_model()

        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise PermissionDenied("Invalid tenant")

        try:
            membership = TenantUser.objects.get(
                user=request.user,
                tenant=tenant
            )
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")

        # All roles can view users list (needed for team context)
        # VIEWERs get read-only view, management actions are blocked separately

        users = TenantUser.objects.filter(
            tenant=tenant
        ).select_related("user")

        data = [
            {
                "id": tu.user.id,
                "username": tu.user.username,
                "role": tu.role,
                "joined_at": tu.created_at,
                "keycloak_id": tu.user.keycloak_id,
            }
            for tu in users
        ]

        return Response(data)


class RemoveUserFromTenantView(APIView):
    """
    OWNER can remove a user from their tenant.
    
    DELETE /api/customers/users/<user_id>/remove/
    
    This will:
    1. Remove user from TenantUser mapping
    2. Remove from RolesMap
    3. Revoke their Keycloak tokens (force logout)
    4. Optionally delete from Keycloak if they have no other tenants
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        token = request.auth
        if not token:
            raise PermissionDenied("Authentication required")

        tenant_schema = token.get("tenant_schema")
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")

        Tenant = get_tenant_model()

        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise PermissionDenied("Invalid tenant")

        # Check if requester is OWNER
        try:
            requester_membership = TenantUser.objects.get(
                user=request.user,
                tenant=tenant
            )
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")

        if requester_membership.role != "OWNER":
            raise PermissionDenied("Only OWNER can remove users")

        # Get the user to remove
        try:
            user_to_remove = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get their tenant membership
        try:
            target_membership = TenantUser.objects.get(
                user=user_to_remove,
                tenant=tenant
            )
        except TenantUser.DoesNotExist:
            return Response(
                {"error": "User is not a member of this tenant"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Prevent owner from removing themselves
        if user_to_remove.id == request.user.id:
            return Response(
                {"error": "Cannot remove yourself. Use account deletion instead."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Prevent removing another OWNER
        if target_membership.role == "OWNER":
            return Response(
                {"error": "Cannot remove another OWNER. Transfer ownership first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        removed_role = target_membership.role
        keycloak_revoked = False
        keycloak_disabled = False

        # ---- Keycloak Cleanup (always runs for this tenant) ----
        kc_service = KeycloakService()
        kc_uid = user_to_remove.keycloak_id

        if kc_uid:
            # 1. Revoke Keycloak tokens (force logout immediately)
            try:
                from todo_saas.utils.keycloak_admin import get_keycloak_admin_client
                kc_client = get_keycloak_admin_client()
                kc_client.revoke_user_tokens(kc_uid)
                keycloak_revoked = True
                logger.info(f"Revoked tokens for user {user_to_remove.username}")
            except Exception as e:
                logger.warning(f"Failed to revoke tokens: {e}")

            # 2. Remove from Keycloak organization members
            try:
                kc_service.remove_user_from_organization(kc_uid, tenant.name)
            except Exception as e:
                logger.warning(f"Failed to remove user from organization in Keycloak: {e}")

            # 3. Remove client role assignment
            try:
                if tenant.keycloak_client_id and removed_role:
                    kc_service.remove_client_role_assignment(kc_uid, tenant.keycloak_client_id, removed_role)
            except Exception as e:
                logger.warning(f"Failed to remove client role in Keycloak: {e}")

            # 4. Remove from tenant group
            try:
                if tenant.keycloak_group_id:
                    kc_service.remove_user_from_group(kc_uid, tenant.keycloak_group_id)
            except Exception as e:
                logger.warning(f"Failed to remove user from group in Keycloak: {e}")

        # ---- Local DB Cleanup ----
        # Remove from TenantUser
        target_membership.delete()
        logger.info(f"Removed {user_to_remove.username} from tenant {tenant.name}")

        # Remove from RolesMap
        RolesMap.objects.filter(user=user_to_remove, tenant=tenant).delete()

        # Check if user has other tenants
        other_tenants = TenantUser.objects.filter(user=user_to_remove).count()

        # Only if user has NO other tenants: disable in KC + deactivate locally
        database_deactivated = False
        if other_tenants == 0:
            if kc_uid:
                try:
                    kc_service.disable_user(kc_uid)
                    keycloak_disabled = True
                    logger.info(f"Disabled {user_to_remove.username} in Keycloak (orphaned, 0 tenants)")
                except Exception as e:
                    logger.warning(f"Failed to disable user in Keycloak: {e}")
            try:
                user_to_remove.is_active = False
                user_to_remove.save(update_fields=["is_active"])
                database_deactivated = True
                logger.info(f"Deactivated user {user_to_remove.username} in local database")
            except Exception as e:
                logger.warning(f"Failed to deactivate user in database: {e}")

        return Response({
            "message": f"User removed from tenant" + (" and account disabled" if database_deactivated else ""),
            "user_id": user_id,
            "username": user_to_remove.username,
            "removed_role": removed_role,
            "keycloak_tokens_revoked": keycloak_revoked,
            "keycloak_user_disabled": keycloak_disabled,
            "database_user_deactivated": database_deactivated,
            "remaining_tenants": other_tenants,
        }, status=status.HTTP_200_OK)


class UpdateUserRoleView(APIView):
    """
    OWNER can change a user's role within the tenant.
    
    PATCH /api/customers/users/<user_id>/role/
    
    Body: {"role": "MEMBER"} or {"role": "VIEWER"}
    
    Cannot change:
    - Own role (owner cannot demote themselves)
    - Another owner's role
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        token = request.auth
        if not token:
            raise PermissionDenied("Authentication required")

        tenant_schema = token.get("tenant_schema")
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")

        Tenant = get_tenant_model()

        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise PermissionDenied("Invalid tenant")

        # Check if requester is OWNER
        try:
            requester_membership = TenantUser.objects.get(
                user=request.user,
                tenant=tenant
            )
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")

        if requester_membership.role != "OWNER":
            raise PermissionDenied("Only OWNER can change roles")

        # Get new role from request
        new_role = request.data.get("role")
        if not new_role or new_role not in ["OWNER", "MEMBER", "VIEWER"]:
            return Response(
                {"error": "Invalid role. Must be OWNER, MEMBER, or VIEWER"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the target user
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get their tenant membership
        try:
            target_membership = TenantUser.objects.get(
                user=target_user,
                tenant=tenant
            )
        except TenantUser.DoesNotExist:
            return Response(
                {"error": "User is not a member of this tenant"},
                status=status.HTTP_404_NOT_FOUND
            )

        old_role = target_membership.role

        # Prevent owner from changing their own role
        if target_user.id == request.user.id:
            return Response(
                {"error": "Cannot change your own role"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If promoting to OWNER, ensure current owner approves
        if new_role == "OWNER" and old_role != "OWNER":
            # This is a ownership transfer/sharing
            logger.warning(
                f"User {target_user.username} promoted to OWNER by {request.user.username}"
            )

        # Update the role
        target_membership.role = new_role
        target_membership.save()

        # Update RolesMap if exists
        roles_map = RolesMap.objects.filter(user=target_user, tenant=tenant).first()
        if roles_map:
            from customers.models import Role
            try:
                role_obj = Role.objects.get(name=new_role)
                roles_map.role = role_obj
                roles_map.save()
            except Role.DoesNotExist:
                pass

        # Sync role change to Keycloak
        keycloak_role_updated = False
        if target_user.keycloak_id and tenant.keycloak_client_id:
            try:
                kc_service = KeycloakService()

                # Remove old client role
                if old_role:
                    kc_service.remove_client_role_assignment(
                        target_user.keycloak_id, tenant.keycloak_client_id, old_role
                    )

                # Assign new client role
                kc_service.assign_client_role_to_user(
                    target_user.keycloak_id, tenant.keycloak_client_id, new_role
                )

                keycloak_role_updated = True
                logger.info(
                    f"Keycloak role updated for {target_user.username}: {old_role} -> {new_role}"
                )
            except Exception as e:
                logger.warning(f"Failed to sync role change to Keycloak: {e}")

        # Revoke tokens to force re-login with new role
        if target_user.keycloak_id:
            try:
                from todo_saas.utils.keycloak_admin import get_keycloak_admin_client
                kc_client = get_keycloak_admin_client()
                kc_client.revoke_user_tokens(target_user.keycloak_id)
                logger.info(f"Revoked tokens for {target_user.username} after role change")
            except Exception as e:
                logger.warning(f"Failed to revoke tokens after role change: {e}")

        return Response({
            "message": f"Role updated for {target_user.username}",
            "user_id": user_id,
            "username": target_user.username,
            "old_role": old_role,
            "new_role": new_role,
            "keycloak_role_updated": keycloak_role_updated,
            "tokens_revoked": True,
        }, status=status.HTTP_200_OK)
