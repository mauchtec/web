from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from GateCore.models import AccessRule
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AccessRequestAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = APIClient()
        self.client.login(username='testuser', password='testpass')
        # Create an access rule for the user
        AccessRule.objects.create(
            name='Test Rule',
            user=self.user,
            location='TestGate',
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timedelta(hours=1)).time(),
            days_of_week=timezone.now().strftime('%a'),
            is_active=True
        )

    def test_access_granted(self):
        url = reverse('access-request')
        data = {'location': 'TestGate', 'method': 'card'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['granted'])
        self.assertIn('granted', response.data['reason'])

    def test_access_denied(self):
        url = reverse('access-request')
        data = {'location': 'WrongGate', 'method': 'card'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['granted'])
        self.assertIn('No matching rule', response.data['reason'])
