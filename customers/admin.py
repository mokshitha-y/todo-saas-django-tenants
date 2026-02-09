from django.contrib import admin
from .models import Client, Organization, Role, RolesMap, TenantUser

# ✅ Always safe
admin.site.register(Client)
admin.site.register(Organization)
admin.site.register(Role)
admin.site.register(RolesMap)
admin.site.register(TenantUser)

# ✅ Defensive registration for Domain
try:
    from .models import Domain
    admin.site.register(Domain)
except Exception:
    # django-tenants loads Domain lazily
    pass
