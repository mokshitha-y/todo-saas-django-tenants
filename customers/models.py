from django.conf import settings
from django.db import models
from django_tenants.models import TenantMixin
import uuid
from datetime import timedelta
from django.utils import timezone


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


class SystemAuditLog(models.Model):
    """
    Audit log for destructive/important operations (survives tenant deletion).
    Lives in PUBLIC schema.
    
    Used for:
    - Tenant deletion (account_deletion_flow)
    - User account deletion (when deleting last tenant)
    - Any operation where tenant schema may not exist after completion
    """
    OPERATION_CHOICES = (
        ("TENANT_CREATED", "Tenant Created"),
        ("TENANT_DELETED", "Tenant Deleted"),
        ("USER_DELETED", "User Permanently Deleted"),
        ("USER_DISABLED", "User Disabled"),
        ("METRICS_REFRESH", "Dashboard Metrics Refresh"),
        ("RECURRING_TODO", "Recurring Todo Processing"),
    )
    
    STATUS_CHOICES = (
        ("STARTED", "Started"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    )
    
    operation = models.CharField(max_length=50, choices=OPERATION_CHOICES)
    tenant_name = models.CharField(max_length=100)  # Name not FK - tenant may be deleted
    schema_name = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    triggered_by = models.CharField(max_length=100, null=True, blank=True)  # username or "system"
    flow_run_id = models.CharField(max_length=100, null=True, blank=True)  # Prefect flow run ID
    details = models.JSONField(null=True, blank=True)  # Additional context
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["tenant_name"]),
            models.Index(fields=["operation"]),
            models.Index(fields=["started_at"]),
        ]
    
    def __str__(self):
        return f"{self.operation} - {self.tenant_name} ({self.status})"


def get_invitation_expiry():
    """Default expiry: 48 hours from now"""
    return timezone.now() + timedelta(hours=48)


class Invitation(models.Model):
    """
    Pending invitation for a user to join a tenant.
    Lives in PUBLIC schema.
    
    Flow:
    1. OWNER creates invitation with email + role
    2. System sends email with unique token link
    3. Invitee clicks link, enters username + password
    4. System creates user accounts (Django + Keycloak)
    5. Invitation marked as used
    """
    ROLE_CHOICES = (
        ("MEMBER", "Member"),
        ("VIEWER", "Viewer"),
    )
    
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("ACCEPTED", "Accepted"),
        ("EXPIRED", "Expired"),
        ("CANCELLED", "Cancelled"),
    )
    
    email = models.EmailField()
    tenant = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="invitations"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="MEMBER")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invitations_sent"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Store the user created when invitation is accepted
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations_accepted"
    )
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
        ]
    
    def __str__(self):
        return f"Invitation: {self.email} → {self.tenant.name} ({self.status})"
    
    @property
    def is_valid(self):
        """Check if invitation can still be accepted"""
        return (
            self.status == "PENDING" and 
            timezone.now() < self.expires_at
        )
    
    def mark_expired(self):
        """Mark invitation as expired"""
        if self.status == "PENDING":
            self.status = "EXPIRED"
            self.save(update_fields=["status"])
    
    def accept(self, user):
        """Mark invitation as accepted"""
        self.status = "ACCEPTED"
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=["status", "accepted_at", "accepted_by"])


class EmailConfiguration(models.Model):
    """
    Per-tenant email configuration for sending invitations.
    Lives in PUBLIC schema.
    
    Allows each organization owner to configure their own SMTP settings
    so that invitation emails are sent from their organization's email.
    """
    tenant = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="email_config"
    )
    
    # SMTP Settings
    smtp_host = models.CharField(max_length=255, default="smtp.gmail.com")
    smtp_port = models.IntegerField(default=587)
    use_tls = models.BooleanField(default=True)
    
    # Credentials (encrypted in production)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)  # App password for Gmail
    
    # Sender info
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=255, blank=True)  # e.g., "Acme Corp"
    
    # Status
    is_verified = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Configuration"
        verbose_name_plural = "Email Configurations"
    
    def __str__(self):
        return f"Email Config for {self.tenant.name}"
    
    def is_configured(self):
        """Check if email is properly configured"""
        return bool(self.smtp_username and self.smtp_password and self.from_email)
    
    def get_from_header(self):
        """Return formatted From header"""
        if self.from_name:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email

