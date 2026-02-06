from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from users.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = ("username", "email", "is_active", "is_staff")
    list_filter = ("is_staff", "is_active")

    fieldsets = UserAdmin.fieldsets
    add_fieldsets = UserAdmin.add_fieldsets
