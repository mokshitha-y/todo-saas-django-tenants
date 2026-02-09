from rest_framework import serializers
from django.contrib.auth import authenticate
from users.models import User
from customers.models import Client, Organization, RolesMap, Role, TenantUser
import logging

logger = logging.getLogger(__name__)


class RegisterSerializer(serializers.Serializer):
    """
    Handles atomic registration: create user, organization, tenant, and Keycloak sync.
    """
    username = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    organization_name = serializers.CharField(max_length=255, required=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def create(self, validated_data):
        """
        Atomic transaction to create:
        1. User in local database
        2. Organization
        3. Client (Tenant with schema)
        4. RolesMap entries
        5. TenantUser entry
        
        This will be called by the view which orchestrates Keycloak sync.
        """
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

        # Create Organization
        organization = Organization.objects.create(
            name=validated_data["organization_name"],
        )

        # Create Client (Tenant) - schema will be auto-created
        client = Client.objects.create(
            name=validated_data["organization_name"],
            organization=organization,
            on_trial=True,
        )

        # Create/ensure default roles exist
        owner_role, _ = Role.objects.get_or_create(
            name="OWNER",
            defaults={"description": "Owner role - full administrative control"}
        )
        member_role, _ = Role.objects.get_or_create(
            name="MEMBER",
            defaults={"description": "Member role - can create and edit own todos"}
        )
        viewer_role, _ = Role.objects.get_or_create(
            name="VIEWER",
            defaults={"description": "Viewer role - read-only access"}
        )

        # Assign OWNER role to registering user
        role_map = RolesMap.objects.create(
            user=user,
            tenant=client,
            role=owner_role,
        )

        # Also create TenantUser entry for backward compatibility
        TenantUser.objects.create(
            user=user,
            tenant=client,
            role="OWNER",
        )

        logger.info(
            f"Created new tenant workspace: {client.name} (schema: {client.schema_name}) "
            f"for user: {user.username}"
        )

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            username=data.get("username"),
            password=data.get("password")
        )

        if not user:
            raise serializers.ValidationError("Invalid username or password")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")

        data["user"] = user
        return data


class InviteUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=["MEMBER", "VIEWER"])


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for user profile information."""
    
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "keycloak_id"]
        read_only_fields = ["id", "keycloak_id"]


class RoleMapSerializer(serializers.ModelSerializer):
    """Serializer for role mappings."""
    role_name = serializers.CharField(source="role.name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = RolesMap
        fields = ["id", "user", "tenant", "role", "role_name", "tenant_name", "created_at"]
        read_only_fields = ["id", "created_at"]
