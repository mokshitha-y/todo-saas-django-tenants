from django.urls import path
from .views import (
    LoginView,
    RegisterView,
    InviteUserView,
    ChangePasswordView,
    ForgotPasswordView,
    ListMyTenantsView,
    SwitchTenantView,
)

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("register/", RegisterView.as_view()),
    path("tenants/", ListMyTenantsView.as_view()),
    path("switch-tenant/", SwitchTenantView.as_view()),
    path("invite/", InviteUserView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
    path("reset-password/", ForgotPasswordView.as_view()),
]
