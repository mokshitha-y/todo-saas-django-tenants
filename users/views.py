from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import authenticate
from django_tenants.utils import schema_context

from customers.models import Client, TenantUser
from users.models import User

import re


# =========================
# JWT HELPER
# =========================

def get_tokens_for_user(user, tenant, role):
    refresh = RefreshToken.for_user(user)

    # 🔑 STANDARDIZED KEYS (VERY IMPORTANT)
    refresh["tenant_schema"] = tenant.schema_name
    refresh["role"] = role

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


# =========================
# REGISTER (PUBLIC)
# =========================

class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        tenant_name = request.data.get("tenant_name")

        if not all([username, password, tenant_name]):
            return Response(
                {"error": "username, password, tenant_name required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema_name = re.sub(r"[^a-z0-9]", "", tenant_name.lower())

        with schema_context("public"):
            # 1️⃣ Create USER
            if User.objects.filter(username=username).exists():
                return Response(
                    {"error": "User already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.create_user(
                username=username,
                password=password,
                is_active=True,
                is_staff=True,
            )

            # 2️⃣ Create TENANT
            if Client.objects.filter(schema_name=schema_name).exists():
                return Response(
                    {"error": "Tenant already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tenant = Client.objects.create(
                schema_name=schema_name,
                name=tenant_name,
            )

            # 3️⃣ Map USER → TENANT
            TenantUser.objects.create(
                user=user,
                tenant=tenant,
                role="OWNER",
            )

        tokens = get_tokens_for_user(user, tenant, "OWNER")

        return Response(
            {
                **tokens,
                "user": {
                    "username": user.username,
                    "role": "OWNER",
                },
                "tenant": {
                    "schema": tenant.schema_name,
                    "name": tenant.name,
                },
            },
            status=status.HTTP_201_CREATED,
        )


# =========================
# LOGIN (PUBLIC)
# =========================

class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        tenant_schema = request.data.get("tenant_schema")  # optional

        if not username or not password:
            return Response(
                {"error": "Username and password required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        memberships = TenantUser.objects.filter(user=user)

        if not memberships.exists():
            return Response(
                {"error": "User not part of any tenant"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Tenant selection
        if tenant_schema:
            try:
                membership = memberships.get(
                    tenant__schema_name=tenant_schema
                )
            except TenantUser.DoesNotExist:
                return Response(
                    {"error": "Invalid tenant"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            if memberships.count() > 1:
                return Response(
                    {
                        "error": "Multiple tenants found",
                        "tenants": [
                            {
                                "schema": m.tenant.schema_name,
                                "name": m.tenant.name,
                            }
                            for m in memberships
                        ],
                    },
                    status=status.HTTP_300_MULTIPLE_CHOICES,
                )
            membership = memberships.first()

        tenant = membership.tenant
        role = membership.role

        tokens = get_tokens_for_user(user, tenant, role)

        return Response(
            {
                **tokens,
                "user": {
                    "username": user.username,
                    "role": role,
                },
                "tenant": {
                    "schema": tenant.schema_name,
                    "name": tenant.name,
                },
            }
        )


# =========================
# INVITE USER (TENANT)
# =========================

class InviteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        inviter = request.user

        # 🔑 FIXED: standardized key
        tenant_schema = request.auth.get("tenant_schema")

        if not tenant_schema:
            return Response(
                {"error": "Tenant context missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = TenantUser.objects.get(
            user=inviter,
            tenant__schema_name=tenant_schema,
        )

        if membership.role != "OWNER":
            return Response(
                {"error": "Only OWNER can invite users"},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = request.data.get("username")
        password = request.data.get("password")
        role = request.data.get("role")

        if not all([username, password, role]):
            return Response(
                {"error": "username, password, role required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role not in ["MEMBER", "VIEWER"]:
            return Response(
                {"error": "Invalid role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context("public"):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"is_active": True},
            )
            if created:
                user.set_password(password)
                user.save()

            tenant = Client.objects.get(schema_name=tenant_schema)

            if TenantUser.objects.filter(user=user, tenant=tenant).exists():
                return Response(
                    {"error": "User already in tenant"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            TenantUser.objects.create(
                user=user,
                tenant=tenant,
                role=role,
            )

        return Response(
            {
                "message": "User invited successfully",
                "username": user.username,
                "role": role,
            },
            status=status.HTTP_201_CREATED,
        )
