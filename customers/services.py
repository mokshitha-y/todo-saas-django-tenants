
import logging
from django.conf import settings
from keycloak import KeycloakAdmin
import requests

logger = logging.getLogger(__name__)


class KeycloakService:
    def __init__(self):
        try:
            self.keycloak_admin = KeycloakAdmin(
                server_url=settings.KEYCLOAK_SERVER_URL,
                username=settings.KEYCLOAK_ADMIN_USER,
                password=settings.KEYCLOAK_ADMIN_PASSWORD,
                realm_name=settings.KEYCLOAK_REALM,
                user_realm_name=getattr(settings, "KEYCLOAK_ADMIN_REALM", "master"),
                verify=True,
            )
            logger.info("[KeycloakService] Admin initialized")
        except Exception as e:
            logger.error(f"[KeycloakService] Failed to init admin: {e}")
            self.keycloak_admin = None

    def get_user_by_email(self, email):
        if not self.keycloak_admin:
            return None
        try:
            users = self.keycloak_admin.get_users({"email": email})
            for user in users:
                if user.get("email", "").lower() == email.lower():
                    logger.info(f"[Keycloak] Found user with email {email}")
                    return user
            logger.info(f"[Keycloak] No user found with email {email}")
            return None
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None

    def create_organization(self, org_name: str, alias: str = None, domain: str = None):
        """
        Create a native Keycloak organization (if Organizations feature is enabled).
        Returns org_id. If already exists, returns existing org_id.
        """
        if not self.keycloak_admin:
            return None
        # Check if organization exists (exact match)
        try:
            orgs = self.keycloak_admin.get_organizations({"name": org_name})
            exact_org = None
            for org in orgs:
                if org.get("name") == org_name:
                    exact_org = org
                    break
            if exact_org:
                logger.info(f"[Keycloak] Organization {org_name} already exists (exact match)")
                return exact_org.get("id")
        except Exception as e:
            logger.warning(f"Failed to check existing organization {org_name}: {e}")
        payload = {
            "name": org_name,
            "alias": alias or org_name,
            "domains": [domain or f"{org_name}.com"],
        }
        try:
            org_id = self.keycloak_admin.create_organization(payload)
            logger.info(f"[Keycloak] Created organization {org_name}")
            return org_id
        except Exception as e:
            if "already exists" in str(e):
                logger.info(f"[Keycloak] Organization {org_name} already exists (409)")
                # Try to fetch existing org
                try:
                    orgs = self.keycloak_admin.get_organizations({"name": org_name})
                    if orgs:
                        return orgs[0].get("id")
                except Exception as e2:
                    logger.warning(f"Failed to fetch existing org after 409: {e2}")
            logger.error(f"Failed to create organization {org_name}: {e}")
            return None

    def create_group(self, group_name: str):
        """
        Create a Keycloak group for organization.
        Returns group_id. If already exists, returns existing group_id.
        """
        if not self.keycloak_admin:
            return None
        # Check if group exists
        try:
            groups = self.keycloak_admin.get_groups({"name": group_name})
            if groups:
                logger.info(f"[Keycloak] Group {group_name} already exists")
                return groups[0].get("id")
        except Exception as e:
            logger.warning(f"Failed to check existing group {group_name}: {e}")
        try:
            group_id = self.keycloak_admin.create_group({"name": group_name})
            logger.info(f"[Keycloak] Created group {group_name}")
            return group_id
        except Exception as e:
            if "already exists" in str(e):
                logger.info(f"[Keycloak] Group {group_name} already exists (409)")
                try:
                    groups = self.keycloak_admin.get_groups({"name": group_name})
                    if groups:
                        return groups[0].get("id")
                except Exception as e2:
                    logger.warning(f"Failed to fetch existing group after 409: {e2}")
            logger.error(f"Failed to create group {group_name}: {e}")
            return None

    def create_client(self, client_name: str):
        """
        Create a Keycloak client (application) with standard OIDC settings.
        Returns client_id.
        """
        if not self.keycloak_admin:
            return None
        try:
            # If a client with this clientId already exists, update it to be public and allow direct grants
            try:
                existing = self.keycloak_admin.get_client_id(client_name)
            except Exception:
                existing = None

            if existing:
                client_id = existing
                try:
                    self.keycloak_admin.update_client(client_id, {"publicClient": True, "directAccessGrantsEnabled": True})
                    logger.info(f"[Keycloak] Updated existing client {client_name} to be public and enable direct grants")
                except Exception as e:
                    logger.warning(f"[Keycloak] Failed to update existing client {client_name}: {e}")
            else:
                client_rep = {
                    "clientId": client_name,
                    "enabled": True,
                    # Make tenant clients public to simplify ROPC (no per-tenant secret storage required)
                    "publicClient": True,
                    "protocol": "openid-connect",
                    "rootUrl": "http://localhost:3000",  # Adjust as needed
                    "redirectUris": ["http://localhost:3000/*"],
                    "baseUrl": "/",
                    "adminUrl": "http://localhost:3000",
                    "standardFlowEnabled": True,
                    "directAccessGrantsEnabled": True,
                    "serviceAccountsEnabled": True,
                }
                client_id = self.keycloak_admin.create_client(client_rep)
                logger.info(f"[Keycloak] Created client {client_name}")

            # Ensure default client roles exist
            for role_name in ["OWNER", "MEMBER", "VIEWER"]:
                try:
                    self.create_client_role(client_id, {"name": role_name}, skip_exists=True)
                    logger.info(f"[Keycloak] Ensured client role {role_name} exists for client {client_name}")
                except Exception as e:
                    logger.warning(f"[Keycloak] Could not ensure role {role_name} for client {client_name}: {e}")

            return client_id
        except Exception as e:
            logger.error(f"Failed to create client {client_name}: {e}")
            return None

    def create_client_role(self, client_id: str, payload: dict, skip_exists: bool = False):
        """
        Wrapper around Keycloak's create_client_role.
        Returns role name on success.
        """
        if not self.keycloak_admin:
            return None
        try:
            return self.keycloak_admin.create_client_role(client_id, payload, skip_exists=skip_exists)
        except Exception as e:
            logger.error(f"Failed to create client role {payload} for client {client_id}: {e}")
            return None

    def get_client_role_id(self, client_id: str, role_name: str):
        if not self.keycloak_admin:
            return None
        try:
            return self.keycloak_admin.get_client_role_id(client_id, role_name)
        except Exception as e:
            logger.error(f"Failed to get client role id for {role_name} in client {client_id}: {e}")
            return None

    def assign_client_role_to_user(self, user_id: str, client_id: str, role_name: str):
        """
        Assign a client role to a user.
        """
        if not self.keycloak_admin:
            return
        try:
            role_id = self.get_client_role_id(client_id, role_name)
            if not role_id:
                # try to create role if it doesn't exist
                self.create_client_role(client_id, {"name": role_name}, skip_exists=True)
                role_id = self.get_client_role_id(client_id, role_name)
            if not role_id:
                logger.warning(f"Client role {role_name} not found for client {client_id}")
                return
            role_repr = {"id": role_id, "name": role_name}
            self.keycloak_admin.assign_client_role(user_id, client_id, [role_repr])
            logger.info(f"[Keycloak] Assigned client role {role_name} to user {user_id} for client {client_id}")
        except Exception as e:
            logger.error(f"Failed to assign client role {role_name} to user {user_id} for client {client_id}: {e}")
            return

    def delete_client_by_id(self, client_id: str):
        """
        Delete a Keycloak client by id.
        """
        if not self.keycloak_admin or not client_id:
            return False
        try:
            self.keycloak_admin.delete_client(client_id)
            logger.info(f"[Keycloak] Deleted client {client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete client {client_id}: {e}")
            return False
    def get_user_by_username(self, username):
        if not self.keycloak_admin:
            return None
        try:
            users = self.keycloak_admin.get_users({"username": username, "exact": True})
            return users[0] if users else None
        except Exception as e:
            logger.error(f"Failed to get user {username}: {e}")
            return None

    def get_or_create_user(self, username, email, password, first_name=None, last_name=None):
        if not self.keycloak_admin:
            return None
        existing = self.get_user_by_username(username)
        if existing:
            uid = existing.get("id")
            # Ensure firstName/lastName are set (required by realm user-profile)
            update_payload = {"requiredActions": [], "enabled": True, "emailVerified": True}
            if not existing.get("firstName"):
                update_payload["firstName"] = first_name or username
            if not existing.get("lastName"):
                update_payload["lastName"] = last_name or username
            try:
                self.keycloak_admin.update_user(uid, update_payload)
            except Exception:
                pass
            # If a password is provided for an existing user (invite flow), ensure it's set
            if password:
                try:
                    self.keycloak_admin.set_user_password(uid, password, temporary=False)
                    logger.info(f"[Keycloak] Ensured password for existing user {username}")
                except Exception as e:
                    logger.warning(f"Failed to set password for existing user {username}: {e}")
            return uid
        try:
            # firstName and lastName are REQUIRED by the Keycloak user-profile
            # configuration; omitting them causes "Account is not fully set up" on ROPC.
            user_id = self.keycloak_admin.create_user({
                "username": username,
                "email": email,
                "firstName": first_name or username,
                "lastName": last_name or username,
                "enabled": True,
                "emailVerified": True,
            })
            logger.info(f"[Keycloak] Created user {username}")

            # Ensure user has no required actions and is fully enabled
            try:
                self.keycloak_admin.update_user(user_id, {"requiredActions": [], "enabled": True, "emailVerified": True})
                logger.info(f"[Keycloak] Cleared required actions for user {username}")
            except Exception as e:
                logger.warning(f"Failed to clear required actions for user {username}: {e}")

            # Explicitly set password using admin endpoint (more reliable for ROPC)
            try:
                if password:
                    self.keycloak_admin.set_user_password(user_id, password, temporary=False)
                    logger.info(f"[Keycloak] Set password for new user {username}")
            except Exception as e:
                logger.warning(f"Failed to set password for new user {username}: {e}")

            return user_id
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return None

    def delete_user(self, user_id):
        if not self.keycloak_admin:
            return
        try:
            self.keycloak_admin.delete_user(user_id)
            logger.info(f"[Keycloak] Deleted user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")

    def disable_user(self, user_id: str) -> bool:
        """Disable a Keycloak user account instead of deleting it.
        Returns True on success, False otherwise."""
        if not self.keycloak_admin or not user_id:
            return False
        try:
            self.keycloak_admin.update_user(user_id, {"enabled": False})
            logger.info(f"[Keycloak] Disabled user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to disable user {user_id}: {e}")
            return False

    def enable_user(self, user_id: str) -> bool:
        """Re-enable a previously disabled Keycloak user account."""
        if not self.keycloak_admin or not user_id:
            return False
        try:
            self.keycloak_admin.update_user(user_id, {"enabled": True})
            logger.info(f"[Keycloak] Enabled user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable user {user_id}: {e}")
            return False

    def delete_client(self, group_id: str):
        """
        Delete tenant GROUP.
        """
        if not self.keycloak_admin or not group_id:
            return
        try:
            self.keycloak_admin.delete_group(group_id)
            logger.info(f"[Keycloak] Deleted group {group_id}")
        except Exception as e:
            logger.error(f"Failed to delete group {group_id}: {e}")

    def add_user_to_organization(self, user_id: str, org_name: str) -> bool:
        """
        Add a user to an organization by name. Returns True on success.
        """
        if not self.keycloak_admin or not user_id or not org_name:
            return False
        try:
            orgs = self.keycloak_admin.get_organizations({"name": org_name})
            if not orgs:
                logger.warning(f"[Keycloak] Organization {org_name} not found")
                return False
            # Find exact match
            org_id = None
            for org in orgs:
                if org.get("name") == org_name:
                    org_id = org.get("id")
                    break
            if not org_id and orgs:
                org_id = orgs[0].get("id")
            if not org_id:
                logger.warning(f"[Keycloak] No organization id for {org_name}")
                return False
            self.keycloak_admin.organization_user_add(user_id, org_id)
            logger.info(f"[Keycloak] Added user {user_id} to organization {org_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add user {user_id} to organization {org_name}: {e}")
            return False
    def change_password(self, username: str, old_password: str, new_password: str) -> dict:
        """
        Change a user's password. Verifies old password via ROPC first,
        then sets new password via admin API.
        Returns {"success": True} or {"success": False, "error": "..."}.
        """
        # Step 1: Verify old password by attempting ROPC
        token_data, err = self._do_ropc(username, old_password)
        if not token_data:
            return {"success": False, "error": "Current password is incorrect"}

        # Step 2: Find user id in Keycloak
        kc_user = self.get_user_by_username(username)
        if not kc_user:
            return {"success": False, "error": "User not found in Keycloak"}

        uid = kc_user["id"]

        # Step 3: Set new password via admin API
        try:
            self.keycloak_admin.set_user_password(uid, new_password, temporary=False)
            logger.info(f"[Keycloak] Password changed for user {username}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[Keycloak] Failed to change password for {username}: {e}")
            return {"success": False, "error": "Failed to update password"}

    def reset_password(self, username: str, email: str, new_password: str) -> dict:
        """
        Reset a user's password after verifying username + email match.
        Used for the forgot-password flow (unauthenticated).
        Returns {"success": True} or {"success": False, "error": "..."}.
        """
        # Step 1: Look up user by username in Keycloak and verify email matches
        kc_user = self.get_user_by_username(username)
        if not kc_user:
            return {"success": False, "error": "No account found with that username"}

        kc_email = (kc_user.get("email") or "").lower().strip()
        provided_email = (email or "").lower().strip()

        if kc_email != provided_email:
            return {"success": False, "error": "Username and email do not match"}

        uid = kc_user["id"]

        # Step 2: Set new password
        try:
            self.keycloak_admin.set_user_password(uid, new_password, temporary=False)
            logger.info(f"[Keycloak] Password reset for user {username}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[Keycloak] Failed to reset password for {username}: {e}")
            return {"success": False, "error": "Failed to reset password"}

    def assign_user_to_client_role(self, user_id: str, group_id: str, role_name=None):
        """
        Add user to tenant group.
        role_name ignored (RBAC handled in Django).
        """
        if not self.keycloak_admin:
            return
        if not user_id or not group_id:
            return
        try:
            self.keycloak_admin.group_user_add(user_id, group_id)
            logger.info(f"[Keycloak] Added user {user_id} to group {group_id}")
        except Exception as e:
            logger.error(f"Failed to add user {user_id} to group {group_id}: {e}")

    # ---------------------
    # New helper methods
    # ---------------------

    def _do_ropc(self, username: str, password: str, client_id: str | None = None):
        """
        Internal: perform a single ROPC token request. Returns (response_json, error_body) tuple.
        When a custom client_id is supplied (tenant-specific public client), no client_secret
        is sent because public clients must authenticate without a secret.
        """
        token_url = f"{settings.KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
        using_global_client = client_id is None
        effective_client_id = client_id or getattr(settings, "KEYCLOAK_CLIENT_ID", None)

        payload = {
            "grant_type": "password",
            "client_id": effective_client_id,
            "username": username,
            "password": password,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Only include client_secret for the global (confidential) backend client.
        # Tenant-specific clients are public and MUST NOT send a secret.
        if using_global_client:
            client_secret = getattr(settings, "KEYCLOAK_CLIENT_SECRET", None)
            if client_secret:
                payload["client_secret"] = client_secret

        resp = requests.post(token_url, data=payload, headers=headers, timeout=10)

        if resp.status_code == 200:
            return resp.json(), None

        try:
            body = resp.json()
        except Exception:
            body = {"error": "unknown", "error_description": resp.text}
        return None, body

    def exchange_password_for_token(self, username: str, password: str, client_id: str | None = None):
        """
        Use Keycloak ROPC grant to exchange username/password for tokens.
        If Keycloak Organization membership blocks ROPC ("Account is not fully set up"),
        temporarily removes the user from all organizations, retries, and re-adds them.
        Returns token response dict on success or None on failure.
        """
        try:
            # Attempt 1: standard ROPC
            token_data, err = self._do_ropc(username, password, client_id)
            if token_data:
                return token_data

            logger.info(f"[Keycloak] ROPC attempt 1 failed for {username}: {err}")

            # Check if it's the "Account is not fully set up" error caused by org membership
            is_account_setup = (
                isinstance(err, dict)
                and err.get("error") == "invalid_grant"
                and "Account is not fully set up" in err.get("error_description", "")
            )

            if not is_account_setup:
                return None

            # Look up user
            kc_user = self.get_user_by_username(username) or self.get_user_by_email(username)
            if not kc_user or not kc_user.get("id"):
                logger.warning(f"[Keycloak] Cannot find user {username} in Keycloak for remediation")
                return None

            uid = kc_user["id"]

            # Clear user-level required actions, ensure firstName/lastName are set
            update_payload = {"requiredActions": [], "enabled": True, "emailVerified": True}
            if not kc_user.get("firstName"):
                update_payload["firstName"] = kc_user.get("username", username)
            if not kc_user.get("lastName"):
                update_payload["lastName"] = kc_user.get("username", username)
            try:
                self.keycloak_admin.update_user(uid, update_payload)
            except Exception as e:
                logger.warning(f"[Keycloak] Failed to update user profile for {uid}: {e}")
            try:
                self.keycloak_admin.set_user_password(uid, password, temporary=False)
            except Exception as e:
                logger.warning(f"[Keycloak] Failed to set password for {uid}: {e}")

            # Attempt 2: temporarily remove user from ALL Keycloak organizations, then retry ROPC
            removed_orgs = []
            try:
                user_orgs = self.keycloak_admin.get_user_organizations(uid)
                logger.info(f"[Keycloak] User {username} belongs to {len(user_orgs)} organization(s): {[o.get('name') for o in user_orgs]}")

                for org in user_orgs:
                    org_id = org.get("id")
                    if org_id:
                        try:
                            self.keycloak_admin.organization_user_remove(uid, org_id)
                            removed_orgs.append(org_id)
                            logger.info(f"[Keycloak] Temporarily removed user {uid} from org {org.get('name')} ({org_id})")
                        except Exception as e:
                            logger.warning(f"[Keycloak] Failed to remove user from org {org_id}: {e}")
            except Exception as e:
                logger.warning(f"[Keycloak] Failed to list user organizations for {uid}: {e}")

            # Now retry ROPC without org membership
            token_data, err2 = self._do_ropc(username, password, client_id)

            # Re-add user to all organizations regardless of ROPC outcome
            for org_id in removed_orgs:
                try:
                    self.keycloak_admin.organization_user_add(uid, org_id)
                    logger.info(f"[Keycloak] Re-added user {uid} to org {org_id}")
                except Exception as e:
                    logger.warning(f"[Keycloak] Failed to re-add user {uid} to org {org_id}: {e}")

            if token_data:
                logger.info(f"[Keycloak] ROPC succeeded for {username} after org-membership remediation")
                return token_data

            logger.warning(f"[Keycloak] ROPC attempt 2 also failed for {username}: {err2}")
            return None

        except Exception as e:
            logger.error(f"[Keycloak] Password grant error for {username}: {e}")
            return None

    def get_userinfo(self, access_token: str):
        """
        Call Keycloak userinfo endpoint using access token and return the JSON payload.
        """
        try:
            userinfo_url = f"{settings.KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            resp = requests.get(userinfo_url, headers=headers, timeout=5)
            if resp.status_code != 200:
                logger.warning(f"[Keycloak] Failed to fetch userinfo: {resp.status_code}")
                return None
            return resp.json()
        except Exception as e:
            logger.error(f"[Keycloak] Userinfo error: {e}")
            return None

    def remove_user_from_group(self, user_id: str, group_id: str):
        """Remove a user from Keycloak group (tenant membership)."""
        if not self.keycloak_admin or not user_id or not group_id:
            return False
        try:
            self.keycloak_admin.group_user_remove(user_id, group_id)
            logger.info(f"[Keycloak] Removed user {user_id} from group {group_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove user {user_id} from group {group_id}: {e}")
            return False

    def get_organization_id(self, org_name: str):
        """Return organization id for an organization name, or None if not found."""
        if not self.keycloak_admin or not org_name:
            return None
        try:
            orgs = self.keycloak_admin.get_organizations({"name": org_name})
            for org in orgs:
                if org.get("name") == org_name:
                    return org.get("id")
            return orgs[0].get("id") if orgs else None
        except Exception as e:
            logger.warning(f"Failed to lookup organization {org_name}: {e}")
            return None

    def remove_user_from_organization(self, user_id: str, org_name: str):
        """Remove a user from a Keycloak organization by name."""
        if not self.keycloak_admin or not user_id or not org_name:
            return False
        try:
            org_id = self.get_organization_id(org_name)
            if not org_id:
                logger.info(f"Organization {org_name} not found in Keycloak, skipping removal")
                return False
            self.keycloak_admin.organization_user_remove(user_id, org_id)
            logger.info(f"[Keycloak] Removed user {user_id} from organization {org_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove user {user_id} from organization {org_name}: {e}")
            return False

    def remove_client_role_assignment(self, user_id: str, client_id: str, role_name: str):
        """Unassign a client role from a user (if present)."""
        if not self.keycloak_admin or not user_id or not client_id or not role_name:
            return False
        try:
            role_id = self.get_client_role_id(client_id, role_name)
            if not role_id:
                logger.info(f"Client role {role_name} not found in client {client_id}")
                return False
            role_repr = {"id": role_id, "name": role_name}
            self.keycloak_admin.delete_client_roles_of_user(user_id, client_id, [role_repr])
            logger.info(f"[Keycloak] Removed client role {role_name} from user {user_id} for client {client_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove client role {role_name} from user {user_id}: {e}")
            return False
