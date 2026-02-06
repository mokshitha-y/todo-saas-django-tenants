from django.conf import settings
from django.db import models
from django_tenants.models import TenantMixin


class Client(TenantMixin):
    """
    Tenant (organization)
    Lives in PUBLIC schema
    """
    name = models.CharField(max_length=100)
    paid_until = models.DateField(null=True, blank=True)
    on_trial = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)

    auto_create_schema = True  # REQUIRED

    def __str__(self):
        return self.name


class TenantUser(models.Model):
    """
    Mapping between PUBLIC users and tenants
    Lives in PUBLIC schema
    """

    ROLE_CHOICES = (
        ("OWNER", "OWNER"),
        ("MEMBER", "MEMBER"),
        ("VIEWER", "VIEWER"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
    )
    tenant = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="users",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "tenant")

    def __str__(self):
        return f"{self.user} → {self.tenant} ({self.role})"
