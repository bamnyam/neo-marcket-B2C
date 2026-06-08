from django.urls import path

from app.buyers.api.controller import LoginController

urlpatterns = [
    path("auth/login", LoginController.as_view(), name="auth-login"),
]
