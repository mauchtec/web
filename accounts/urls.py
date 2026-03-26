from django.urls import path

from .views import (
    RegistrationView,
    RoleListView,
    LoginView,
    LogoutView,
    RegisterPageView,
    LoginPageView,
    LogoutPageView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path("roles/", RoleListView.as_view(), name="role_list"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register-ui/", RegisterPageView.as_view(), name="register_page"),
    path("login-ui/", LoginPageView.as_view(), name="login_page"),
    path("logout-ui/", LogoutPageView.as_view(), name="logout_page"),
]
