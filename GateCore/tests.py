
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import date

from .models import Site, Person, Property, Unit, Occupancy
from .services.mobile_auth import normalize_phone
from .views import OccupancySerializer

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


class InternalExtensionPhoneTests(APITestCase):
	def test_normalize_phone_keeps_internal_extension(self):
		self.assertEqual(normalize_phone("1002"), "1002")

	def test_person_allows_internal_extension(self):
		person = Person.objects.create(
			first_name="Ext",
			last_name="1002",
			phone="1002",
		)
		self.assertEqual(person.phone, "1002")


class OccupancySerializerPhoneTests(APITestCase):
	def test_person_phone_uses_actual_phone_not_device_identifier(self):
		site = Site.objects.create(
			name="Serializer Estate",
			site_type="estate",
			location="Test City",
			address="123 Test Lane",
			description="Serializer test estate",
			code="SER123",
		)
		property_obj = Property.objects.create(
			site=site,
			name="Serializer Property",
			property_type="residential",
			address="123 Test Lane",
			description="Serializer property",
			code="PROP123",
		)
		unit = Unit.objects.create(
			property=property_obj,
			unit_code="A-101",
			floor_number=1,
			unit_type="apartment",
		)
		person = Person.objects.create(
			first_name="Resident",
			last_name="Example",
			phone="+27656231093",
			device_identifier="b23cb34603b59826",
		)
		occupancy = Occupancy.objects.create(
			person=person,
			unit=unit,
			role="tenant",
			start_date=date.today(),
		)

		data = OccupancySerializer(occupancy).data

		self.assertEqual(data["person_phone"], "+27656231093")
