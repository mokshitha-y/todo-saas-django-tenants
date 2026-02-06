from django.urls import path, include

urlpatterns = [
    # Public auth only (register + login)
    path("api/auth/", include("users.urls")),
]
