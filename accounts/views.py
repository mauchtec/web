from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.urls import reverse_lazy
from django.shortcuts import redirect

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.generic import TemplateView

from .serializers import ROLE_MAPPING, RegistrationSerializer


class RegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "role": serializer.validated_data["role"],
                "token": token.key,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Logged out"})


class RoleListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        roles = []
        for key, config in ROLE_MAPPING.items():
            roles.append(
                {
                    "key": key,
                    "group": config["group"],
                    "is_staff": config["is_staff"],
                    "is_superuser": config["is_superuser"],
                }
            )
        return Response({"roles": roles})


class RegisterPageView(TemplateView):
    template_name = "frontend/auth/register.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = [
            {"key": key, "label": key.replace("_", " ").title()}
            for key in ROLE_MAPPING.keys()
        ]
        context["errors"] = getattr(self, "errors", None)
        return context

    def post(self, request, *args, **kwargs):
        serializer = RegistrationSerializer(data=request.POST)
        if serializer.is_valid():
            user = serializer.save()
            auth_login(request, user)
            return redirect("/")
        self.errors = serializer.errors
        return self.get(request, *args, **kwargs)


class LoginPageView(TemplateView):
    template_name = "frontend/auth/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["errors"] = getattr(self, "errors", None)
        return context

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None:
            self.errors = {"detail": ["Invalid credentials"]}
            return self.get(request, *args, **kwargs)
        auth_login(request, user)
        return redirect("/")


class LogoutPageView(TemplateView):
    template_name = "frontend/auth/logout.html"
    extra_context = {"logout_url": reverse_lazy("accounts:logout")}

    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        auth_logout(request)
        return redirect("accounts:login_page")
