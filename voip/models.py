import uuid
from django.db import models
from django.conf import settings


class VoipCall(models.Model):
    CALL_STATUS_CHOICES = [
        ('', 'Pending'),
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('busy', 'Busy'),
        ('no-answer', 'No Answer'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voip_calls',
    )
    provider_call_id = models.CharField(max_length=255, blank=True)
    resident_id = models.UUIDField(null=True, blank=True)
    destination = models.CharField(max_length=50, blank=True)
    pin = models.CharField(max_length=20, blank=True)
    pin_source = models.CharField(max_length=50, blank=True)
    call_status = models.CharField(max_length=30, choices=CALL_STATUS_CHOICES, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    recording_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"VoipCall {self.id} → {self.destination} [{self.call_status or 'pending'}]"
