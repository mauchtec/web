
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from .models import Site

class HealthCheckAPITest(APITestCase):
	def test_health_check(self):
		url = reverse('health_check')
		response = self.client.get(url)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data, {'status': 'ok'})

from django.contrib.auth import get_user_model

class SiteAPITest(APITestCase):
	def setUp(self):
		self.client = APIClient()
		self.site_data = {
			'name': 'Test Estate',
			'site_type': 'estate',
			'location': 'Test City',
			'address': '123 Test Lane',
			'description': 'A test estate',
			'code': 'EST123',
		}
		# Create and authenticate a test user
		User = get_user_model()
		self.user = User.objects.create_user(username='apitestuser', password='testpass123')
		self.client.force_authenticate(user=self.user)

	def test_create_site(self):
		url = reverse('site-list')
		response = self.client.post(url, self.site_data, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(Site.objects.count(), 1)
		self.assertEqual(Site.objects.get().name, 'Test Estate')

	def test_list_sites(self):
		Site.objects.create(**self.site_data)
		url = reverse('site-list')
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data['results']), 1)

	def test_retrieve_site(self):
		site = Site.objects.create(**self.site_data)
		url = reverse('site-detail', args=[site.id])
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['name'], 'Test Estate')

	def test_update_site(self):
		site = Site.objects.create(**self.site_data)
		url = reverse('site-detail', args=[site.id])
		response = self.client.patch(url, {'name': 'Updated Estate'}, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		site.refresh_from_db()
		self.assertEqual(site.name, 'Updated Estate')

	def test_delete_site(self):
		site = Site.objects.create(**self.site_data)
		url = reverse('site-detail', args=[site.id])
		response = self.client.delete(url)
		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertEqual(Site.objects.count(), 0)
