from django.db import models
from customers.models import Client

class DashboardMetrics(models.Model):
    """
    aggregated metrics per tenant, stored in PUBLIC schema
    """
    tenant = models.OneToOneField(Client, on_delete=models.CASCADE, related_name="metrics")
    total_users = models.IntegerField(default=0)
    todos_new = models.IntegerField(default=0)
    todos_completed = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Metrics for {self.tenant.name}"
