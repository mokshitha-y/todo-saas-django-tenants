from django.urls import path
from .views import LoginView, RegisterView, InviteUserView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("register/", RegisterView.as_view()),
    path("invite/", InviteUserView.as_view()),
]
