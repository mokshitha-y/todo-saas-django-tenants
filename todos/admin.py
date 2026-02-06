from django.contrib import admin
from .models import Todo


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "is_completed", "created_at")

    def _is_public_admin(self, user):
        """
        Public admin users (auth.User) do not have `role`.
        They should have full access.
        """
        return not hasattr(user, "role")

    def has_view_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        if self._is_public_admin(request.user):
            return True
        return request.user.role in ["OWNER", "MEMBER"]

    def has_change_permission(self, request, obj=None):
        if self._is_public_admin(request.user):
            return True
        if obj is None:
            return True
        return obj.can_edit(request.user)

    def has_delete_permission(self, request, obj=None):
        if self._is_public_admin(request.user):
            return True
        if obj is None:
            return False
        return obj.can_delete(request.user)


