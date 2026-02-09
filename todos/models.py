from django.db import models
from users.models import User
from simple_history.models import HistoricalRecords


class Todo(models.Model):
    RECURRENCE_CHOICES = (
        ("NONE", "No Recurrence"),
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    due_date = models.DateTimeField(null=True, blank=True)
    
    # Recurring todo fields
    recurrence_type = models.CharField(
        max_length=10,
        choices=RECURRENCE_CHOICES,
        default="NONE",
    )
    parent_todo = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurring_instances",
        help_text="Reference to the original recurring todo"
    )
    
    history = HistoricalRecords()

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_todos"
    )

    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_todos"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    # ===== RBAC HELPERS =====
    def can_view(self, user):
        return True

    def can_edit(self, user):
        if user.role == "OWNER":
            return True
        if user.role == "MEMBER" and (
            self.created_by_id == user.id or self.assigned_to_id == user.id
        ):
            return True
        return False

    def can_delete(self, user):
        return user.role == "OWNER"

    def __str__(self):
        return self.title
