from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from .models import Todo
from .serializers import TodoSerializer
from customers.models import TenantUser


class TodoViewSet(viewsets.ModelViewSet):
    serializer_class = TodoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Todo.objects.all().order_by("-created_at")

    # =========================
    # TENANT + ROLE RESOLUTION
    # =========================
    def _get_membership(self, request):
        tenant_schema = request.auth.get("tenant_schema") if request.auth else None
        if not tenant_schema:
            raise PermissionDenied("Tenant context missing")

        try:
            return TenantUser.objects.get(
                user=request.user,
                tenant__schema_name=tenant_schema
            )
        except TenantUser.DoesNotExist:
            raise PermissionDenied("User not part of this tenant")

    # =========================
    # CREATE
    # =========================
    def perform_create(self, serializer):
        membership = self._get_membership(self.request)

        if membership.role not in ["OWNER", "MEMBER"]:
            raise PermissionDenied("You cannot create todos")

        serializer.save(created_by=self.request.user)

    # =========================
    # UPDATE / EDIT
    # =========================
    def update(self, request, *args, **kwargs):
        todo = self.get_object()
        membership = self._get_membership(request)

        if membership.role == "VIEWER":
            return Response(
                {"detail": "You cannot edit todos"},
                status=status.HTTP_403_FORBIDDEN
            )

        if membership.role == "MEMBER" and todo.created_by_id != request.user.id:
            return Response(
                {"detail": "Members can only edit their own todos"},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        todo = self.get_object()
        membership = self._get_membership(request)

        if membership.role == "VIEWER":
            return Response(
                {"detail": "You cannot update todos"},
                status=status.HTTP_403_FORBIDDEN
            )

        if membership.role == "MEMBER" and todo.created_by_id != request.user.id:
            return Response(
                {"detail": "Members can only update their own todos"},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ THIS LINE FIXES TOGGLE
        return super().partial_update(request, *args, **kwargs)

    # =========================
    # DELETE
    # =========================
    def destroy(self, request, *args, **kwargs):
        membership = self._get_membership(request)

        if membership.role != "OWNER":
            return Response(
                {"detail": "Only OWNER can delete todos"},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)

    # =========================
    # TOGGLE COMPLETE
    # =========================
    @action(detail=True, methods=["post"])
    def toggle_complete(self, request, pk=None):
        todo = self.get_object()
        membership = self._get_membership(request)

        if membership.role == "VIEWER":
            return Response(
                {"detail": "You cannot update status"},
                status=status.HTTP_403_FORBIDDEN
            )

        if membership.role == "MEMBER" and todo.created_by_id != request.user.id:
            return Response(
                {"detail": "Members can only update their own todos"},
                status=status.HTTP_403_FORBIDDEN
            )

        todo.is_completed = not todo.is_completed
        todo.save(update_fields=["is_completed"])

        return Response(
            {"id": todo.id, "is_completed": todo.is_completed}
        )
