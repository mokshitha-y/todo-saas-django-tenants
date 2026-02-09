from rest_framework import serializers
from .models import Todo
from customers.models import TenantUser


class TodoSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(source="assigned_to.username", read_only=True, allow_null=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Todo
        fields = [
            "id",
            "title",
            "description",
            "is_completed",
            "is_deleted",
            "due_date",
            "is_overdue",
            "recurrence_type",
            "parent_todo",
            "created_at",
            "updated_at",
            "created_by",
            "assigned_to",
            "assigned_to_username",
        ]
        read_only_fields = ["created_at", "updated_at", "created_by", "is_overdue", "parent_todo"]

    def get_created_by(self, instance):
        request = self.context.get("request")
        role = None

        if request and request.auth:
            tenant_schema = request.auth.get("tenant_schema")
            if tenant_schema:
                try:
                    membership = TenantUser.objects.get(
                        user=instance.created_by,
                        tenant__schema_name=tenant_schema
                    )
                    role = membership.role
                except TenantUser.DoesNotExist:
                    role = None

        return {
            "id": instance.created_by.id,
            "username": instance.created_by.username,
            "role": role,
        }

    def get_is_overdue(self, instance):
        """Check if todo is overdue."""
        from django.utils import timezone
        
        if not instance.due_date or instance.is_completed:
            return False
        
        return instance.due_date < timezone.now()


class TodoCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating todos.
    
    Note: Audit trail is handled automatically by django-simple-history (HistoricalRecords).
    """

    class Meta:
        model = Todo
        fields = [
            "title",
            "description",
            "is_completed",
            "due_date",
            "assigned_to",
            "recurrence_type",
        ]

    def validate_title(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Title cannot be empty.")
        return value
