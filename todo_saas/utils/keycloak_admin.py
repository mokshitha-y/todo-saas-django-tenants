import logging
from keycloak import KeycloakAdmin
from django.conf import settings

logger = logging.getLogger(__name__)


class KeycloakAdminClient:
    """
    Official Keycloak Admin wrapper.
    Uses python-keycloak ONLY.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self) -> KeycloakAdmin:
        if not self._client:
            self._client = KeycloakAdmin(
                server_url=settings.KEYCLOAK_SERVER_URL,
                username=settings.KEYCLOAK_ADMIN_USER,
                password=settings.KEYCLOAK_ADMIN_PASSWORD,
                realm_name=settings.KEYCLOAK_REALM,
                user_realm_name=getattr(settings, "KEYCLOAK_ADMIN_REALM", "master"),
                verify=True,
            )
            logger.info("[Keycloak] Admin client initialized")
        return self._client

    # ---------- USERS ----------

    def revoke_user_tokens(self, user_id: str) -> bool:
        try:
            self.client.logout_all_sessions(user_id)
            return True
        except Exception:
            return False

    def delete_user(self, user_id: str) -> bool:
        try:
            self.client.delete_user(user_id)
            logger.info(f"[Keycloak] Deleted user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[Keycloak] Delete user failed: {e}")
            return False

    def disable_user(self, user_id: str) -> bool:
        """Disable a Keycloak user (soft-delete). Preserves audit trail."""
        try:
            self.client.update_user(user_id, {"enabled": False})
            logger.info(f"[Keycloak] Disabled user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[Keycloak] Disable user failed: {e}")
            return False

    def remove_user_from_organization(self, user_id: str, org_name: str) -> bool:
        """Remove a user from a Keycloak organization by name."""
        try:
            orgs = self.client.get_organizations({"name": org_name})
            org_id = None
            for org in orgs:
                if org.get("name") == org_name:
                    org_id = org.get("id")
                    break
            if not org_id and orgs:
                org_id = orgs[0].get("id")
            if not org_id:
                logger.warning(f"[Keycloak] Org {org_name} not found for user removal")
                return False
            self.client.organization_user_remove(user_id, org_id)
            logger.info(f"[Keycloak] Removed user {user_id} from org {org_name}")
            return True
        except Exception as e:
            logger.warning(f"[Keycloak] Remove user from org failed: {e}")
            return False

    def remove_client_role(self, user_id: str, client_id: str, role_name: str) -> bool:
        """Remove a client role from a user."""
        try:
            role_id = self.client.get_client_role_id(client_id, role_name)
            if not role_id:
                return False
            self.client.delete_client_roles_of_user(user_id, client_id, [{"id": role_id, "name": role_name}])
            logger.info(f"[Keycloak] Removed role {role_name} from user {user_id}")
            return True
        except Exception as e:
            logger.warning(f"[Keycloak] Remove client role failed: {e}")
            return False

    # ---------- GROUPS (TENANT ORG) ----------

    def delete_group(self, group_id: str) -> bool:
        try:
            self.client.delete_group(group_id)
            logger.info(f"[Keycloak] Deleted group {group_id}")
            return True
        except Exception as e:
            logger.error(f"[Keycloak] Delete group failed: {e}")
            return False

    def delete_client(self, client_id: str) -> bool:
        try:
            self.client.delete_client(client_id)
            logger.info(f"[Keycloak] Deleted client {client_id}")
            return True
        except Exception as e:
            logger.error(f"[Keycloak] Delete client failed: {e}")
            return False

    def delete_organization_by_name(self, org_name: str) -> bool:
        """
        Delete an organization by name. Returns True on success.
        """
        try:
            orgs = self.client.get_organizations({"name": org_name})
            if not orgs:
                logger.warning(f"[Keycloak] Organization {org_name} not found")
                return False
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
            self.client.delete_organization(org_id)
            logger.info(f"[Keycloak] Deleted organization {org_name} ({org_id})")
            return True
        except Exception as e:
            logger.error(f"[Keycloak] Failed to delete organization {org_name}: {e}")
            return False

def get_keycloak_admin_client() -> KeycloakAdminClient:
    return KeycloakAdminClient()
