import re
import logging

from django.db import transaction
from django_tenants.utils import schema_context

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from customers.models import Client, TenantUser, Organization, Role
from customers.services import KeycloakService
from users.models import User

logger = logging.getLogger(__name__)

# =========================
# JWT HELPER
# =========================

def get_tokens_for_user(user, tenant, role):
    refresh = RefreshToken.for_user(user)
    refresh["tenant_schema"] = tenant.schema_name
    refresh["role"] = role

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

# =========================
# REGISTER
# =========================

class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):

        organization_name = (request.data.get("tenant_name") or request.data.get("organization_name") or "").strip()
        username = (request.data.get("username") or "").strip()
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password")
        if not all([organization_name, username, email, password]):
            return Response(
                {"error": "organization_name, username, email, and password required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # log inputs for debugging
        logger.info("Register attempt: org=%s username=%s email=%s", organization_name, username, email)

        keycloak = KeycloakService()
        kc_user_id = None
        kc_client_id = None

        # Normalize email for checks
        email_lower = email.strip().lower()

        try:
            # Check username in Keycloak and Django first
            existing_kc_user = keycloak.get_user_by_username(username)
            logger.info("Keycloak user lookup for username=%s returned=%s", username, bool(existing_kc_user))
            if existing_kc_user and existing_kc_user.get("username") == username:
                return Response(
                    {"error": "Username already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if User.objects.filter(username=username).exists():
                logger.info("Local DB: username %s already exists", username)
                return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

            # Check email in Keycloak and Django before attempting create (avoid misleading "email exists" on other failures)
            existing_by_email_kc = keycloak.get_user_by_email(email_lower)
            if existing_by_email_kc:
                logger.info("Keycloak: user with email %s already exists", email_lower)
                return Response(
                    {"error": "User with this email already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if User.objects.filter(email__iexact=email_lower).exists():
                logger.info("Local DB: email %s already exists", email_lower)
                return Response(
                    {"error": "User with this email already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            kc_user_id = keycloak.get_or_create_user(username, email, password)

            if not kc_user_id:
                # Only show "email already exists" if we can confirm email is taken; else generic failure
                existing_now = keycloak.get_user_by_email(email_lower)
                if existing_now:
                    return Response(
                        {"error": "User with this email already exists"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                logger.error("Failed to create Keycloak user for username=%s email=%s", username, email)
                return Response(
                    {"error": "Account creation failed. Try a different username or email, or check Keycloak is reachable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Always use a unique domain for Keycloak org to avoid conflicts
            import uuid
            unique_suffix = str(uuid.uuid4())[:8]
            org_domain = f"{organization_name.lower().replace(' ', '-')}-{unique_suffix}.com"
            kc_org_id = keycloak.create_organization(organization_name, alias=organization_name, domain=org_domain)
            kc_client_id = keycloak.create_client(organization_name)
            # Create or fetch a Keycloak group for the tenant and add the user to it
            # Try to create a Keycloak group name that is unique across tenants.
            kc_group_id = None
            for attempt in range(5):
                proposed_group_name = f"{organization_name}-{unique_suffix}-{attempt}"
                group_id = keycloak.create_group(proposed_group_name)
                # If group_id is already used by another tenant, try a new name
                from django.db.models import Q

                if group_id and not Client.objects.filter(keycloak_group_id=group_id).exists():
                    kc_group_id = group_id
                    break
                logger.warning(
                    "Group id %s already assigned to another tenant, retrying...",
                    group_id,
                )

            if not kc_group_id:
                # Last resort: create group with a UUID suffix (non-deterministic)
                import uuid as _uuid

                proposed_group_name = f"{organization_name}-{_uuid.uuid4().hex[:8]}"
                kc_group_id = keycloak.create_group(proposed_group_name)

            # Add user to that group (if present)
            if kc_group_id:
                keycloak.assign_user_to_client_role(kc_user_id, kc_group_id)
        except Exception as e:
            logger.error(f"Keycloak error: {e}")
            return Response(
                {"error": "Keycloak integration failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            with schema_context("public"):
                with transaction.atomic():
                    if User.objects.filter(username=username).exists():
                        raise Exception("User already exists")
                    if Client.objects.filter(schema_name=organization_name).exists():
                        raise Exception("Tenant already exists")
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        is_active=True,
                        is_staff=True,
                    )
                    # Do not store password locally - Keycloak is the source of truth for authentication
                    user.set_unusable_password()
                    user.keycloak_id = kc_user_id
                    user.save(update_fields=["keycloak_id"])
                    organization = Organization.objects.create(
                        name=organization_name,
                        description=f"Organization for {organization_name}",
                    )
                    # Create tenant without keycloak_group_id first, we'll set it after ensuring uniqueness
                    tenant = Client.objects.create(
                        schema_name=organization_name,
                        name=organization_name,
                        organization=organization,
                        keycloak_client_id=kc_client_id,
                    )

                    # Add owner to Keycloak organization members for visibility
                    try:
                        if kc_user_id:
                            keycloak.add_user_to_organization(kc_user_id, organization_name)
                    except Exception as e:
                        logger.warning("Failed to add owner to organization in Keycloak: %s", e)

                    # Assign OWNER client role to user in Keycloak
                    try:
                        if kc_user_id and kc_client_id:
                            keycloak.assign_client_role_to_user(kc_user_id, kc_client_id, "OWNER")
                    except Exception as e:
                        logger.warning("Failed to assign OWNER client role in Keycloak: %s", e)


                    # Persist group id only if it isn't already used (double-check)
                    if kc_group_id:
                        try:
                            if not Client.objects.filter(keycloak_group_id=kc_group_id).exists():
                                tenant.keycloak_group_id = kc_group_id
                                tenant.save(update_fields=["keycloak_group_id"])
                            else:
                                logger.warning(
                                    "kc_group_id %s already owned by another tenant, skipping assignment",
                                    kc_group_id,
                                )
                        except Exception as e:
                            logger.warning(
                                "Could not save keycloak_group_id for tenant %s: %s",
                                tenant.schema_name,
                                e,
                            )

                    owner_role = Role.objects.get(name="OWNER")
                    tenant_user, created_tu = TenantUser.objects.get_or_create(
                        user=user,
                        tenant=tenant,
                        defaults={"role": owner_role.name},
                    )
                    if not created_tu and tenant_user.role != owner_role.name:
                        tenant_user.role = owner_role.name
                        tenant_user.save(update_fields=["role"])

                    # Create RolesMap entry and store keycloak role id for OWNER role
                    from customers.models import RolesMap
                    try:
                        owner_role_obj = owner_role
                        owner_role_id = keycloak.get_client_role_id(kc_client_id, "OWNER") if kc_client_id else None
                        rm, created_rm = RolesMap.objects.get_or_create(
                            user=user,
                            tenant=tenant,
                            role=owner_role_obj,
                            defaults={"keycloak_role_id": owner_role_id},
                        )
                        if not created_rm and owner_role_id and rm.keycloak_role_id != owner_role_id:
                            rm.keycloak_role_id = owner_role_id
                            rm.save(update_fields=["keycloak_role_id"])
                    except Exception as e:
                        logger.warning("Could not create RolesMap for owner: %s", e)
        except Exception as e:
            logger.error(f"DB error: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tokens = get_tokens_for_user(user, tenant, "OWNER")
        return Response(
            {
                **tokens,
                "user": {"username": user.username, "email": user.email, "role": "OWNER"},
                "tenant": {
                    "schema": tenant.schema_name,
                    "name": tenant.name,
                },
            },
            status=status.HTTP_201_CREATED,
        )

# =========================
# LOGIN
# =========================

class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        tenant_schema = request.data.get("tenant_schema")

        # Use Keycloak for authentication (password grant)
        keycloak = KeycloakService()

        # Resolve the user locally first to get the canonical username (email login support)
        user_obj = None
        try:
            user_obj = User.objects.get(username=username)
        except User.DoesNotExist:
            users_by_email = list(User.objects.filter(email=username))
            if len(users_by_email) == 1:
                user_obj = users_by_email[0]
                username = user_obj.username
            elif len(users_by_email) > 1:
                return Response({"error": "Multiple accounts match this email. Please login with username."}, status=400)

        # Try ROPC: prefer global (confidential) client first — it has proper scopes
        token_resp = keycloak.exchange_password_for_token(username, password)

        # If realm has "Email as username", Keycloak may expect email in the username param; try with email
        if not token_resp and user_obj and getattr(user_obj, "email", None) and user_obj.email != username:
            token_resp = keycloak.exchange_password_for_token(user_obj.email, password)

        if not token_resp:
            return Response({"error": "Invalid username/email or password"}, status=401)

        # Extract user info: first try userinfo endpoint, then decode JWT as fallback
        access_token = token_resp.get("access_token")
        userinfo = keycloak.get_userinfo(access_token) or {}

        # If userinfo endpoint fails, decode the access_token JWT to extract claims
        if not userinfo.get("sub") and access_token:
            try:
                import json, base64
                payload_b64 = access_token.split(".")[1]
                # Add padding
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload_b64))
                userinfo = {
                    "sub": claims.get("sub"),
                    "preferred_username": claims.get("preferred_username"),
                    "email": claims.get("email"),
                }
            except Exception as e:
                logger.warning(f"Failed to decode JWT: {e}")

        kc_id = userinfo.get("sub")
        preferred_username = userinfo.get("preferred_username")
        email = userinfo.get("email")

        # Find local user by keycloak_id first, then by username/email
        user = None
        if kc_id:
            try:
                user = User.objects.get(keycloak_id=kc_id)
            except User.DoesNotExist:
                user = None

        if not user and preferred_username:
            try:
                user = User.objects.get(username=preferred_username)
            except User.DoesNotExist:
                user = None

        if not user and email:
            try:
                users_by_email = list(User.objects.filter(email=email))
                if len(users_by_email) == 1:
                    user = users_by_email[0]
                elif len(users_by_email) > 1:
                    return Response({"error": "Multiple accounts match this email. Please login with username."}, status=400)
            except Exception:
                user = None

        if not user:
            # No local mapping exists, deny access (tenant membership missing)
            return Response({"error": "No tenant access"}, status=403)

        memberships = TenantUser.objects.filter(user=user).select_related("tenant")
        if not memberships.exists():
            return Response({"error": "No tenant access"}, status=403)

        if tenant_schema:
            membership = memberships.filter(tenant__schema_name=tenant_schema).first()
        else:
            # Default: prefer company org (non-personal) so members land there first
            from customers.services import PERSONAL_SCHEMA_PREFIX
            non_personal = [m for m in memberships if not m.tenant.schema_name.startswith(PERSONAL_SCHEMA_PREFIX)]
            membership = (non_personal[0] if non_personal else memberships.first())

        tokens = get_tokens_for_user(
            user,
            membership.tenant,
            membership.role,
        )

        from customers.services import PERSONAL_SCHEMA_PREFIX
        all_memberships = TenantUser.objects.filter(user=user).select_related("tenant")
        tenants = [
            {
                "schema": m.tenant.schema_name,
                "name": m.tenant.name,
                "role": m.role,
                "is_personal": m.tenant.schema_name.startswith(PERSONAL_SCHEMA_PREFIX),
            }
            for m in all_memberships
        ]

        return Response(
            {
                **tokens,
                "user": {"username": user.username, "role": membership.role},
                "tenant": {
                    "schema": membership.tenant.schema_name,
                    "name": membership.tenant.name,
                },
                "tenants": tenants,
                "keycloak": {"access_token": access_token, "id_token": token_resp.get("id_token")},
            },
            status=status.HTTP_200_OK,
        )

# =========================
# TENANTS LIST & SWITCH (for multi-tenant / personal org)
# =========================

class ListMyTenantsView(APIView):
    """Return all tenants (organisations) the current user belongs to."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from customers.services import PERSONAL_SCHEMA_PREFIX

        memberships = TenantUser.objects.filter(user=request.user).select_related("tenant")
        tenants = []
        for m in memberships:
            schema = m.tenant.schema_name
            tenants.append({
                "schema": schema,
                "name": m.tenant.name,
                "role": m.role,
                "is_personal": schema.startswith(PERSONAL_SCHEMA_PREFIX),
            })
        return Response({"tenants": tenants})


class SwitchTenantView(APIView):
    """Return new JWT for the given tenant_schema so the user can act in that org."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant_schema = request.data.get("tenant_schema")
        if not tenant_schema:
            return Response({"error": "tenant_schema required"}, status=400)
        membership = TenantUser.objects.filter(
            user=request.user,
            tenant__schema_name=tenant_schema,
        ).select_related("tenant").first()
        if not membership:
            return Response({"error": "Not a member of this organisation"}, status=403)
        tokens = get_tokens_for_user(request.user, membership.tenant, membership.role)
        return Response({
            **tokens,
            "user": {"username": request.user.username, "role": membership.role},
            "tenant": {"schema": membership.tenant.schema_name, "name": membership.tenant.name},
        })


# =========================
# INVITE USER
# =========================

class InviteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        inviter = request.user
        tenant_schema = request.data.get("tenant_schema")
        email = request.data.get("email")
        password = request.data.get("password")
        role_name = request.data.get("role")

        if role_name not in ["MEMBER", "VIEWER"]:
            return Response({"error": "Invalid role"}, status=400)

        username = request.data.get("username")
        if not username or not username.strip():
            return Response({"error": "username is required"}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=400)

        if not email:
            return Response({"error": "email is required"}, status=400)

        # basic email sanity check
        if "@" not in email:
            return Response({"error": "invalid email"}, status=400)

        # If tenant_schema not provided, and inviter is OWNER of exactly one tenant,
        # use that tenant automatically. Frontends may omit tenant_schema.
        if not tenant_schema:
            owner_memberships = TenantUser.objects.filter(user=inviter, role="OWNER")
            if owner_memberships.count() == 1:
                tenant_schema = owner_memberships.first().tenant.schema_name
            else:
                return Response({"error": "tenant_schema required"}, status=400)

        inviter_membership = TenantUser.objects.filter(
            user=inviter,
            tenant__schema_name=tenant_schema,
            role="OWNER",
        ).first()

        if not inviter_membership:
            # Log detailed info to help debugging why inviter isn't recognized as OWNER
            inviter_memberships = list(
                TenantUser.objects.filter(user=inviter).values(
                    "tenant__schema_name", "tenant__name", "role"
                )
            )
            logger.warning(
                "Invite failed: inviter=%s tenant_schema=%s memberships=%s",
                inviter.username,
                tenant_schema,
                inviter_memberships,
            )
            # In DEBUG include memberships in response to aid developer; otherwise keep generic message
            from django.conf import settings

            if getattr(settings, "DEBUG", False):
                return Response(
                    {
                        "error": "Only OWNER can invite",
                        "inviter_memberships": inviter_memberships,
                    },
                    status=403,
                )

            return Response({"error": "Only OWNER can invite"}, status=403)

        logger.info(
            "Invite request: inviter=%s tenant_schema=%s payload=%s",
            inviter.username,
            tenant_schema,
            {"email": email, "role": role_name},
        )

        try:
            keycloak = KeycloakService()

            with schema_context("public"):
                user, created = User.objects.get_or_create(username=username, defaults={"email": email})

                if created:
                    # If no password provided, generate a random temporary password (for Keycloak only)
                    if not password:
                        import secrets

                        password = secrets.token_urlsafe(12)
                    # Do not set local password; rely on Keycloak for auth
                    user.set_unusable_password()
                    user.email = email
                    user.save()
                else:
                    # Ensure email is set for existing user
                    if not user.email and email:
                        user.email = email
                        user.save(update_fields=["email"])
                tenant = Client.objects.get(schema_name=tenant_schema)
                org_name = tenant.name

                if TenantUser.objects.filter(user=user, tenant=tenant).exists():
                    return Response({"error": "Already member"}, status=400)

                kc_user_id = keycloak.get_or_create_user(username, email, password)
                user.keycloak_id = kc_user_id
                user.save(update_fields=["keycloak_id"])
                # Ensure tenant has a Keycloak group and add user to it
                group_id = tenant.keycloak_group_id
                if not group_id:
                    # Try multiple candidate group names until we find a group id not used by another tenant
                    group_id = None
                    for i in range(5):
                        candidate = f"{tenant.name}-{tenant.schema_name}-{i}"
                        candidate_id = keycloak.create_group(candidate)
                        if not candidate_id:
                            continue
                        if not Client.objects.filter(keycloak_group_id=candidate_id).exists():
                            group_id = candidate_id
                            try:
                                tenant.keycloak_group_id = group_id
                                tenant.save(update_fields=["keycloak_group_id"])
                            except Exception as e:
                                logger.warning(
                                    "Could not save keycloak_group_id for tenant %s: %s",
                                    tenant.schema_name,
                                    e,
                                )
                            break
                        logger.warning("Candidate group id %s already used by another tenant, trying next", candidate_id)

                    if not group_id:
                        # Last resort: generate a uuid-suffixed name and attempt once
                        import uuid as _uuid
                        candidate = f"{tenant.name}-{tenant.schema_name}-{_uuid.uuid4().hex[:8]}"
                        group_id = keycloak.create_group(candidate)
                        try:
                            if group_id and not Client.objects.filter(keycloak_group_id=group_id).exists():
                                tenant.keycloak_group_id = group_id
                                tenant.save(update_fields=["keycloak_group_id"])
                        except Exception as e:
                            logger.warning(
                                "Could not save keycloak_group_id for tenant %s on final attempt: %s",
                                tenant.schema_name,
                                e,
                            )

                # Assign user to tenant group in Keycloak
                keycloak.assign_user_to_client_role(
                    kc_user_id,
                    group_id,
                    role_name=role_name,
                )

                # Assign client role in Keycloak (so roles appear under Client -> Roles)
                try:
                    if tenant.keycloak_client_id:
                        keycloak.assign_client_role_to_user(kc_user_id, tenant.keycloak_client_id, role_name)
                        # store RolesMap with Keycloak role id
                        role_obj = Role.objects.get(name=role_name)
                        role_id = keycloak.get_client_role_id(tenant.keycloak_client_id, role_name)
                        from customers.models import RolesMap
                        rm, created_rm = RolesMap.objects.get_or_create(
                            user=user,
                            tenant=tenant,
                            role=role_obj,
                            defaults={"keycloak_role_id": role_id},
                        )
                        if not created_rm and role_id and rm.keycloak_role_id != role_id:
                            rm.keycloak_role_id = role_id
                            rm.save(update_fields=["keycloak_role_id"])
                except Exception as e:
                    logger.warning("Could not assign client role or create RolesMap: %s", e)

                # Also add user to Keycloak organization membership (so they appear in Org -> Members)
                try:
                    if hasattr(keycloak, "add_user_to_organization"):
                        ok = keycloak.add_user_to_organization(kc_user_id, tenant.name)
                        if not ok:
                            logger.warning("Could not add user %s to Keycloak organization %s", kc_user_id, tenant.name)
                    else:
                        logger.debug("KeycloakService.add_user_to_organization not implemented")
                except Exception as e:
                    logger.exception("Error adding user to Keycloak organization: %s", e)

                # Create or update TenantUser atomically to avoid unique constraint errors
                tenant_user, created_tu = TenantUser.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={"role": role_name},
                )
                if not created_tu and tenant_user.role != role_name:
                    tenant_user.role = role_name
                    tenant_user.save(update_fields=["role"])
            return Response(
                {"message": "User invited successfully"},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            # Log exception with stack trace and payload for debugging
            logger.exception(
                "Invite failed: inviter=%s tenant_schema=%s payload=%s error=%s",
                inviter.username,
                tenant_schema,
                {"email": email, "role": role_name},
                str(e),
            )
            from django.conf import settings

            if getattr(settings, "DEBUG", False):
                return Response({"error": "Invite failed", "details": str(e)}, status=500)

            return Response({"error": "Invite failed"}, status=500)


# =========================
# CHANGE PASSWORD (authenticated)
# =========================

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response({"error": "old_password and new_password are required"}, status=400)

        if len(new_password) < 8:
            return Response({"error": "New password must be at least 8 characters"}, status=400)

        if old_password == new_password:
            return Response({"error": "New password must be different from old password"}, status=400)

        keycloak = KeycloakService()
        result = keycloak.change_password(request.user.username, old_password, new_password)

        if result["success"]:
            return Response({"message": "Password changed successfully"}, status=200)
        else:
            return Response({"error": result["error"]}, status=400)


# =========================
# FORGOT / RESET PASSWORD (unauthenticated)
# =========================

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email")
        new_password = request.data.get("new_password")

        if not username or not email or not new_password:
            return Response({"error": "username, email, and new_password are required"}, status=400)

        if len(new_password) < 8:
            return Response({"error": "New password must be at least 8 characters"}, status=400)

        keycloak = KeycloakService()
        result = keycloak.reset_password(username, email, new_password)

        if result["success"]:
            return Response({"message": "Password reset successfully. You can now log in."}, status=200)
        else:
            return Response({"error": result["error"]}, status=400)
