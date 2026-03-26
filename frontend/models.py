from django.db import models

class DummySite(models.Model):
	name = models.CharField(max_length=100)

class DummyDevice(models.Model):
	name = models.CharField(max_length=100)

class AccessPoint(models.Model):
	name = models.CharField(max_length=100)
	access_point_type = models.CharField(max_length=50)
	location = models.CharField(max_length=100)
	site = models.ForeignKey(DummySite, on_delete=models.CASCADE, related_name='access_points')
	devices = models.ManyToManyField(DummyDevice, related_name='access_points')

	def get_access_point_type_display(self):
		return self.access_point_type
