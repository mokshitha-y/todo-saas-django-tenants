from django.contrib import admin
from .models import Client

# ✅ Always safe
admin.site.register(Client)

# ✅ Defensive registration for Domain
try:
    from .models import Domain
    admin.site.register(Domain)
except Exception:
    # django-tenants loads Domain lazily
    pass
