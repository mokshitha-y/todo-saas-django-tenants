from django.db import models


class DashboardMetrics(models.Model):
    """
    Aggregated metrics per tenant.
    Lives in TENANT SCHEMA (no FK to tenant - schema IS the tenant).
    
    Updated by: dashboard_aggregation_flow (Prefect)
    """
    total_users = models.IntegerField(default=0)
    todos_new = models.IntegerField(default=0)
    todos_completed = models.IntegerField(default=0)
    todos_deleted = models.IntegerField(default=0)
    total_todos = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Dashboard Metrics"

    def __str__(self):
        return f"Metrics (updated: {self.updated_at})"


class OrchestrationLog(models.Model):
    """
    Flow execution logs per tenant.
    Lives in TENANT SCHEMA (no FK to tenant - schema IS the tenant).
    
    Used for:
    - Dashboard aggregation runs
    - Recurring todo processing
    - Tenant-specific operations (not destructive)
    """
    FLOW_CHOICES = (
        ("DASHBOARD_AGGREGATION", "Dashboard Aggregation"),
        ("RECURRING_TODO", "Recurring Todo Processing"),
        ("TENANT_REGISTRATION", "Tenant Registration"),
    )
    
    STATUS_CHOICES = (
        ("STARTED", "Started"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    )
    
    flow_name = models.CharField(max_length=50, choices=FLOW_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    flow_run_id = models.CharField(max_length=100, null=True, blank=True)  # Prefect run ID
    triggered_by = models.CharField(max_length=100, null=True, blank=True)  # username or "system"
    details = models.JSONField(null=True, blank=True)  # e.g., {"todos_created": 3}
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["flow_name"]),
            models.Index(fields=["started_at"]),
        ]
    
    def __str__(self):
        return f"{self.flow_name} - {self.status} ({self.started_at})"
