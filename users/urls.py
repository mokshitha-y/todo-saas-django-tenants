from django.urls import path
from .views import LoginView, RegisterView, InviteUserView, ChangePasswordView, ForgotPasswordView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("register/", RegisterView.as_view()),
    path("invite/", InviteUserView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
    path("reset-password/", ForgotPasswordView.as_view()),
]
