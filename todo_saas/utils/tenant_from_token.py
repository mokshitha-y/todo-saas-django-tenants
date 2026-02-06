from django_tenants.utils import get_tenant_model
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import connection

from customers.models import TenantUser


class TenantFromTokenMiddleware(MiddlewareMixin):
    """
    Resolve tenant AND tenant-specific role from JWT token.

    - Always starts in PUBLIC schema
    - Skips admin & debug URLs
    - Switches schema based on JWT tenant_schema
    - Attaches tenant role to request.user.role
    """

    def process_request(self, request):
        # ✅ ALWAYS start in public schema
        connection.set_schema_to_public()

        # ✅ Skip admin & debug routes
        if request.path.startswith("/admin") or request.path.startswith("/__debug__"):
            return

        auth = JWTAuthentication()

        try:
            auth_result = auth.authenticate(request)
        except Exception:
            return

        if not auth_result:
            return

        user, token = auth_result

        # ✅ Read tenant schema from JWT
        tenant_schema = token.payload.get("tenant_schema")
        if not tenant_schema:
            return

        Tenant = get_tenant_model()

        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
            connection.set_tenant(tenant)
        except Tenant.DoesNotExist:
            connection.set_schema_to_public()
            return

        # =====================================
        # ✅ ATTACH TENANT ROLE TO USER OBJECT
        # =====================================
        try:
            tenant_user = TenantUser.objects.get(
                user=user,
                tenant=tenant
            )
            user.role = tenant_user.role
        except TenantUser.DoesNotExist:
            # User exists but has no role in this tenant
            user.role = None

        # Ensure request.user is updated
        request.user = user
