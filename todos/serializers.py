from rest_framework import serializers
from .models import Todo
from customers.models import TenantUser


class TodoSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = Todo
        fields = [
            "id",
            "title",
            "description",
            "is_completed",
            "created_at",
            "created_by",
        ]
        read_only_fields = ["created_at", "created_by"]

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
