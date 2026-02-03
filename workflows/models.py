from django.db import models
import uuid

class Workflow(models.Model):
	STATUS_CHOICES = [
		('draft', 'Draft'),
		('published', 'Published'),
	]

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	name = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	version = models.CharField(max_length=32, default='1.0.0')
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')
	definition = models.JSONField()
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.name} (v{self.version})"
