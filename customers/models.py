from django.conf import settings
from django.db import models
from django_tenants.models import TenantMixin


class Organization(models.Model):
    """
    Organization / Company.
    Lives in PUBLIC schema.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Optional: if you ever use per-org realm
    keycloak_realm = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Client(TenantMixin):
    """
    Tenant (organization) – PostgreSQL schema.
    Lives in PUBLIC schema.
    """
    name = models.CharField(max_length=100)
    paid_until = models.DateField(null=True, blank=True)
    on_trial = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)

    # ✅ KEYCLOAK UUIDS (VERY IMPORTANT)
    keycloak_group_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )
    keycloak_client_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="client",
    )

    auto_create_schema = True

    def __str__(self):
        return self.name


class Role(models.Model):
    """
    Role definitions for RBAC.
    Lives in PUBLIC schema.
    """
    ROLE_CHOICES = (
        ("OWNER", "Owner"),
        ("MEMBER", "Member"),
        ("VIEWER", "Viewer"),
    )

    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class RolesMap(models.Model):
    """
    Fast lookup table for RBAC.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_mappings",
    )
    tenant = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="role_mappings",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="mappings",
    )

    # Optional: Keycloak role UUID
    keycloak_role_id = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "tenant")

    def __str__(self):
        return f"{self.user.username} - {self.role.name} in {self.tenant.name}"


class TenantUser(models.Model):
    """
    Mapping between users and tenants.
    Lives in PUBLIC schema.
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
