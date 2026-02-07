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

class WorkflowSubmission(models.Model):
	"""Store workflow execution data submitted by users"""
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='submissions')
	submission_data = models.JSONField(help_text='User-entered data from workflow execution')
	submitted_at = models.DateTimeField(auto_now_add=True)
	submitted_by = models.CharField(max_length=255, blank=True, help_text='Optional user identifier')
	session_id = models.CharField(max_length=100, blank=True, help_text='Optional session tracking')
	
	class Meta:
		ordering = ['-submitted_at']
		indexes = [
			models.Index(fields=['workflow', '-submitted_at']),
			models.Index(fields=['submitted_at']),
		]
	
	def __str__(self):
		return f"Submission for {self.workflow.name} at {self.submitted_at}"
