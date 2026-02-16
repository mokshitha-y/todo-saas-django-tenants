"""
Invitation System Views (Keycloak Email Integration)

Handles the invitation workflow:
1. OWNER sends invitation → POST /api/customers/invitations/
   - Creates user in Keycloak (without password)
   - Keycloak sends "Set Password" email
   - Creates Invitation record for tracking
2. User clicks KC email link → Sets password in Keycloak
3. User logs in → Backend creates TenantUser on first login if invitation exists
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework import status

from django.conf import settings
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from customers.models import Invitation, TenantUser, RolesMap, Role
from customers.services import KeycloakService, create_personal_tenant_for_user
from users.models import User

import logging
import secrets

logger = logging.getLogger(__name__)



class SendInvitationView(APIView):
    """
    OWNER sends an invitation to an email address using Keycloak.
    
    POST /api/customers/invitations/
    Body: {"email": "user@example.com", "role": "MEMBER"}
    
    Flow:
    1. Creates/finds user in Keycloak
    2. Adds user to KC organization and assigns role
    3. Keycloak sends "Set Password" email
    4. Creates Django User + TenantUser immediately
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        token = request.auth
        if not token:
            raise PermissionDenied("Authentication required")
        
        tenant_schema = token.get("tenant_schema")
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")
        
        # Validate input
        email = request.data.get("email", "").strip().lower()
        role = request.data.get("role", "MEMBER")
        
        if not email or "@" not in email:
            return Response({"error": "Valid email required"}, status=400)
        
        if role not in ["MEMBER", "VIEWER"]:
            return Response({"error": "Invalid role. Must be MEMBER or VIEWER"}, status=400)
        
        Tenant = get_tenant_model()
        
        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise PermissionDenied("Invalid tenant")
        
        # Check if requester is OWNER
        try:
            membership = TenantUser.objects.get(user=request.user, tenant=tenant)
            if membership.role != "OWNER":
                raise PermissionDenied("Only OWNER can send invitations")
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")
        
        # Check if user already exists in this tenant
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if TenantUser.objects.filter(user=existing_user, tenant=tenant).exists():
                return Response({
                    "error": f"User with email {email} is already a member of this organization"
                }, status=400)
        
        # Check for pending invitation
        pending = Invitation.objects.filter(
            email=email,
            tenant=tenant,
            status="PENDING",
            expires_at__gt=timezone.now()
        ).first()
        
        if pending:
            # Resend Keycloak email for existing pending invitation
            try:
                keycloak = KeycloakService()
                kc_user = keycloak.get_user_by_email(email)
                if kc_user:
                    keycloak.send_execute_actions_email(
                        kc_user.get("id"),
                        actions=["UPDATE_PASSWORD"],
                        lifespan=172800  # 48 hours
                    )
                    return Response({
                        "message": f"Resent invitation email to {email}",
                        "invitation_id": str(pending.token),
                        "expires_at": pending.expires_at.isoformat(),
                        "email_sent": True
                    })
            except Exception as e:
                logger.warning(f"Failed to resend KC email: {e}")
            
            return Response({
                "error": f"A pending invitation already exists for {email}",
                "invitation_id": str(pending.token)
            }, status=400)
        
        # Initialize Keycloak
        keycloak = KeycloakService()
        
        # Generate a username from email
        email_prefix = email.split("@")[0]
        username = email_prefix
        
        # Ensure username is unique
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{email_prefix}{counter}"
            counter += 1
        
        try:
            with schema_context("public"):
                # Create or get Keycloak user
                kc_user_id = keycloak.create_invited_user(
                    username=username,
                    email=email,
                    first_name=email_prefix.title(),
                    last_name=tenant.name
                )
                
                if not kc_user_id:
                    # User might already exist - try to get them
                    kc_user = keycloak.get_user_by_email(email)
                    if kc_user:
                        kc_user_id = kc_user.get("id")
                        username = kc_user.get("username", username)
                    else:
                        return Response({
                            "error": "Failed to create user in authentication system"
                        }, status=500)
                
                # Add user to Keycloak organization
                if tenant.name:
                    try:
                        keycloak.add_user_to_organization(kc_user_id, tenant.name)
                    except Exception as e:
                        logger.warning(f"Failed to add user to KC org: {e}")
                
                # Add to Keycloak group
                if tenant.keycloak_group_id:
                    try:
                        keycloak.assign_user_to_client_role(kc_user_id, tenant.keycloak_group_id)
                    except Exception as e:
                        logger.warning(f"Failed to add to KC group: {e}")
                
                # Assign client role in Keycloak
                if tenant.keycloak_client_id:
                    try:
                        keycloak.assign_client_role_to_user(
                            kc_user_id,
                            tenant.keycloak_client_id,
                            role
                        )
                        logger.info(f"Assigned KC client role {role} to user {kc_user_id}")
                    except Exception as e:
                        logger.warning(f"Failed to assign KC role: {e}")
                
                # Create or get Django user
                if existing_user:
                    user = existing_user
                else:
                    user = User.objects.create(
                        username=username,
                        email=email,
                        keycloak_id=kc_user_id,
                        is_active=True
                    )
                    user.set_unusable_password()
                    user.save()
                
                # Create TenantUser mapping NOW (user is invited)
                tenant_user, created = TenantUser.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={"role": role}
                )
                
                if not created:
                    return Response({
                        "error": f"User with email {email} is already a member of this organization"
                    }, status=400)
                
                # Create RolesMap if Role exists
                try:
                    role_obj = Role.objects.get(name=role)
                    RolesMap.objects.get_or_create(
                        user=user,
                        tenant=tenant,
                        role=role_obj
                    )
                except Role.DoesNotExist:
                    pass
                
                # Part 2 (B2): Create personal org for MEMBER/VIEWER so they can invite others there
                if role in ("MEMBER", "VIEWER"):
                    try:
                        create_personal_tenant_for_user(user, kc_user_id, keycloak)
                    except Exception as e:
                        logger.warning("Failed to create personal tenant for invited user %s: %s", email, e)
                
                # Create invitation record for tracking
                invitation = Invitation.objects.create(
                    email=email,
                    tenant=tenant,
                    role=role,
                    created_by=request.user
                )
                
                # Send Keycloak's "Set Password" email
                email_sent = False
                try:
                    email_sent = keycloak.send_execute_actions_email(
                        kc_user_id,
                        actions=["UPDATE_PASSWORD"],
                        lifespan=172800  # 48 hours
                    )
                    if email_sent:
                        logger.info(f"Keycloak sent password setup email to {email}")
                except Exception as e:
                    logger.error(f"Failed to trigger KC email: {e}")
                
                # Mark invitation as accepted since user is created
                invitation.status = "ACCEPTED"
                invitation.accepted_at = timezone.now()
                invitation.accepted_by = user
                invitation.save()
                
                response_data = {
                    "message": f"Invitation sent to {email}",
                    "email_sent": email_sent,
                    "username": username,
                    "role": role
                }
                
                if not email_sent:
                    response_data["warning"] = (
                        "Email could not be sent via Keycloak. "
                        "Please ensure SMTP is configured in Keycloak Realm Settings > Email. "
                        "The user account has been created - they can use 'Forgot Password' to set their password."
                    )
                    # Provide forgot password hint
                    response_data["forgot_password_hint"] = (
                        f"User can go to the login page and click 'Forgot Password' with email: {email}"
                    )
                
                return Response(response_data, status=201)
                
        except Exception as e:
            logger.error(f"Failed to create invitation: {e}")
            return Response({
                "error": f"Failed to create invitation: {str(e)}"
            }, status=500)


class ValidateInvitationView(APIView):
    """
    Validate an invitation token (public endpoint).
    
    GET /api/customers/invitations/{token}/
    
    Returns invitation details if valid.
    Note: With Keycloak flow, invitations are marked ACCEPTED immediately.
    This endpoint is kept for backwards compatibility.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related('tenant').get(token=token)
        except Invitation.DoesNotExist:
            return Response({"error": "Invalid invitation"}, status=404)
        
        # Check if expired
        if timezone.now() > invitation.expires_at:
            invitation.mark_expired()
            return Response({"error": "Invitation has expired"}, status=410)
        
        if invitation.status == "ACCEPTED":
            return Response({
                "valid": True,
                "status": "ACCEPTED",
                "message": "This invitation has been processed. Please check your email for the password setup link, or use 'Forgot Password' on the login page.",
                "email": invitation.email,
                "organization": invitation.tenant.name
            })
        
        if invitation.status != "PENDING":
            return Response({
                "error": f"Invitation is no longer valid (status: {invitation.status})"
            }, status=410)
        
        # Check if email already has an account
        existing_user = User.objects.filter(email=invitation.email).first()
        
        return Response({
            "valid": True,
            "email": invitation.email,
            "organization": invitation.tenant.name,
            "role": invitation.role,
            "invited_by": invitation.created_by.username if invitation.created_by else "Unknown",
            "expires_at": invitation.expires_at.isoformat(),
            "user_exists": existing_user is not None
        })


class AcceptInvitationView(APIView):
    """
    Legacy endpoint for accepting invitations.
    
    With Keycloak flow, users are created immediately on invite.
    This endpoint is kept for backwards compatibility but now just
    returns info about the invitation status.
    
    POST /api/customers/invitations/{token}/accept/
    """
    permission_classes = [AllowAny]
    
    def post(self, request, token):
        try:
            invitation = Invitation.objects.select_related('tenant').get(token=token)
        except Invitation.DoesNotExist:
            return Response({"error": "Invalid invitation"}, status=404)
        
        # With new KC flow, invitation is already accepted and user created
        if invitation.status == "ACCEPTED":
            return Response({
                "message": "Your account has been created! Please check your email for the password setup link from Keycloak, or use 'Forgot Password' on the login page.",
                "organization": invitation.tenant.name,
                "email": invitation.email,
                "status": "already_processed"
            })
        
        if invitation.status == "EXPIRED":
            return Response({"error": "Invitation has expired"}, status=410)
        
        if invitation.status == "CANCELLED":
            return Response({"error": "Invitation was cancelled"}, status=410)
        
        # If somehow still PENDING (shouldn't happen with new flow)
        return Response({
            "error": "Please use the link sent to your email by the authentication system",
            "status": invitation.status
        }, status=400)


class ListInvitationsView(APIView):
    """
    List all invitations for the current tenant (OWNER only).
    
    GET /api/customers/invitations/
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
        
        # Check if requester is OWNER
        try:
            membership = TenantUser.objects.get(user=request.user, tenant=tenant)
            if membership.role != "OWNER":
                raise PermissionDenied("Only OWNER can view invitations")
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")
        
        invitations = Invitation.objects.filter(tenant=tenant).order_by('-created_at')
        
        # Mark expired ones
        for inv in invitations:
            if inv.status == "PENDING" and timezone.now() > inv.expires_at:
                inv.mark_expired()
        
        data = [
            {
                "id": str(inv.token),
                "token": str(inv.token),
                "email": inv.email,
                "role": inv.role,
                "status": inv.status,
                "created_at": inv.created_at.isoformat(),
                "expires_at": inv.expires_at.isoformat(),
                "invited_by": inv.created_by.username if inv.created_by else None,
                "accepted_by": inv.accepted_by.username if inv.accepted_by else None,
            }
            for inv in invitations
        ]
        
        return Response({"invitations": data})


class CancelInvitationView(APIView):
    """
    Cancel a pending invitation (OWNER only).
    
    DELETE /api/customers/invitations/{token}/
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, token):
        auth_token = request.auth
        if not auth_token:
            raise PermissionDenied("Authentication required")
        
        tenant_schema = auth_token.get("tenant_schema")
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")
        
        Tenant = get_tenant_model()
        
        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise PermissionDenied("Invalid tenant")
        
        # Check if requester is OWNER
        try:
            membership = TenantUser.objects.get(user=request.user, tenant=tenant)
            if membership.role != "OWNER":
                raise PermissionDenied("Only OWNER can cancel invitations")
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")
        
        try:
            invitation = Invitation.objects.get(token=token, tenant=tenant)
        except Invitation.DoesNotExist:
            return Response({"error": "Invitation not found"}, status=404)
        
        if invitation.status != "PENDING":
            return Response({
                "error": f"Cannot cancel invitation (status: {invitation.status})"
            }, status=400)
        
        invitation.status = "CANCELLED"
        invitation.save(update_fields=["status"])
        
        return Response({"message": "Invitation cancelled"})


class ResendInvitationView(APIView):
    """
    Resend an invitation email (OWNER only).
    
    POST /api/customers/invitations/{token}/resend/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, token):
        auth_token = request.auth
        if not auth_token:
            raise PermissionDenied("Authentication required")
        
        tenant_schema = auth_token.get("tenant_schema")
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")
        
        Tenant = get_tenant_model()
        
        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise PermissionDenied("Invalid tenant")
        
        # Check if requester is OWNER
        try:
            membership = TenantUser.objects.get(user=request.user, tenant=tenant)
            if membership.role != "OWNER":
                raise PermissionDenied("Only OWNER can resend invitations")
        except TenantUser.DoesNotExist:
            raise PermissionDenied("Not a tenant member")
        
        try:
            invitation = Invitation.objects.get(token=token, tenant=tenant)
        except Invitation.DoesNotExist:
            return Response({"error": "Invitation not found"}, status=404)
        
        if invitation.status != "PENDING":
            return Response({
                "error": f"Cannot resend invitation (status: {invitation.status})"
            }, status=400)
        
        # Extend expiry
        from datetime import timedelta
        invitation.expires_at = timezone.now() + timedelta(hours=48)
        invitation.save(update_fields=["expires_at"])
        
        # Resend Keycloak "Set Password" email
        try:
            invitee = User.objects.filter(email=invitation.email).first()
            kc_user_id = getattr(invitee, "keycloak_id", None) if invitee else None
            if kc_user_id:
                keycloak = KeycloakService()
                keycloak.send_execute_actions_email(
                    kc_user_id,
                    actions=["UPDATE_PASSWORD"],
                    lifespan=172800,
                )
                logger.info(f"Invitation resent: {invitation.email}")
        except Exception as e:
            logger.error(f"Failed to resend invitation email: {e}")
            return Response({"error": "Failed to send email"}, status=500)
        
        return Response({
            "message": f"Invitation resent to {invitation.email}",
            "expires_at": invitation.expires_at.isoformat()
        })
