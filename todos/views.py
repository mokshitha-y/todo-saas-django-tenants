from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from .models import Todo
from .serializers import TodoSerializer, TodoCreateUpdateSerializer
from customers.models import TenantUser


class TodoViewSet(viewsets.ModelViewSet):
    serializer_class = TodoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Use the write-enabled serializer for create/update operations
        if self.action in ("create", "update", "partial_update", "destroy", "toggle_complete"):
            return TodoCreateUpdateSerializer
        return TodoSerializer

    def get_queryset(self):
        # Filter out soft-deleted items
        return Todo.objects.filter(is_deleted=False).order_by("-created_at")

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

        # Soft delete is tracked by HistoricalRecords automatically
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

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Return simple_history entries for this todo with RBAC.
        
        RBAC Rules:
        - OWNER: Can view history of all todos
        - MEMBER: Can view history of their own todos only
        - VIEWER: No access to history
        """
        todo = self.get_object()
        membership = self._get_membership(request)
        
        # VIEWER: No access to history
        if membership.role == "VIEWER":
            return Response(
                {"detail": "Viewers cannot access todo history"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # MEMBER: Can only view history of their own todos
        if membership.role == "MEMBER" and todo.created_by_id != request.user.id:
            return Response(
                {"detail": "Members can only view history of their own todos"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # OWNER: Full access (no additional check needed)
        
        hist_manager = getattr(todo, "history", None)
        if hist_manager is None:
            return Response([], status=status.HTTP_200_OK)

        # Call .all() to get an iterable queryset from the history manager
        hist_qs = hist_manager.all()

        User = get_user_model()
        history_user_ids = [
            h.history_user_id
            for h in hist_qs
            if getattr(h, "history_user_id", None)
        ]
        user_map = {
            u.id: u.username
            for u in User.objects.filter(id__in=history_user_ids).only("id", "username")
        }

        entries = []
        for h in hist_qs.order_by("-history_date"):
            entries.append({
                "history_id": getattr(h, "history_id", None),
                "history_date": getattr(h, "history_date", None),
                "history_type": getattr(h, "history_type", None),
                "history_user_id": getattr(h, "history_user_id", None),
                "history_user": user_map.get(getattr(h, "history_user_id", None)),
                "title": getattr(h, "title", None),
                "description": getattr(h, "description", None),
                "is_completed": getattr(h, "is_completed", None),
                "assigned_to_id": getattr(h, "assigned_to_id", None),
            })

        return Response(entries)
