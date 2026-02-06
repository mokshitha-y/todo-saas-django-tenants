from django.db import models
from users.models import User


class Todo(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)

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
