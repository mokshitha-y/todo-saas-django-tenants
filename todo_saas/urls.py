from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Tenant auth (login, invite)
    path("api/auth/", include("users.urls")),

    # Tenant todos ✅
    path("api/todos/", include("todos.urls")),
]
