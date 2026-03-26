from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .utils import ensure_workflow_role_groups


class RegistrationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_workflow_role_groups(verbosity=0)

    def setUp(self):
        self.url = reverse("accounts:register")

    def test_register_operator_assigns_group(self):
        payload = {
            "username": "operator1",
            "email": "op@example.com",
            "password": "complexpass123",
            "role": "operator",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(username="operator1")
        self.assertTrue(Group.objects.get(name="Operator") in user.groups.all())
        self.assertFalse(user.is_superuser)

    def test_register_superuser_makes_superuser(self):
        payload = {
            "username": "root",
            "email": "root@example.com",
            "password": "superpass123",
            "role": "superuser",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(username="root")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.groups.filter(name="Admin").exists())

    def test_login_and_logout_cycle(self):
        payload = {
            "username": "cycle",
            "email": "cycle@example.com",
            "password": "cyclepass123",
            "role": "operator",
        }
        register = self.client.post(self.url, payload, format="json")
        token = register.json()["token"]
        login = self.client.post(reverse("accounts:login"), {"username": "cycle", "password": "cyclepass123"}, format="json")
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn("token", login.json())
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        logout = self.client.post(reverse("accounts:logout"))
        self.assertEqual(logout.status_code, status.HTTP_200_OK)

    def test_ui_pages_render(self):
        self.assertEqual(self.client.get(reverse("accounts:register_page")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("accounts:login_page")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("accounts:logout_page")).status_code, status.HTTP_200_OK)
