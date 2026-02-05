import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from GateCore.models.people import Person
from GateCore.models.property import Unit

class AuditTrail(models.Model):
    ACTION_CHOICES = [
        ("move", "Move/Reallocate Person"),
        ("link", "Link Person to Unit"),
        ("unlink", "Unlink Person from Unit"),
        ("edit", "Edit Person"),
        ("create", "Create Person"),
        ("update_unit", "Edit Unit"),
        ("create_unit", "Create Unit"),
        ("delete_unit", "Delete Unit"),
    ]
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="audit_trails", null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="audit_trails", null=True, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Trail"
        verbose_name_plural = "Audit Trails"

    def __str__(self):
        who = self.performed_by.username if self.performed_by else "System"
        return f"{self.get_action_display()} by {who} at {self.timestamp:%Y-%m-%d %H:%M}"


class BlockHistory(models.Model):
    """Audit trail for blocking/unblocking entities"""
    
    ENTITY_TYPE_CHOICES = (
        ("person", "Person"),
        ("vehicle", "Vehicle"),
    )
    
    ACTION_CHOICES = (
        ("blocked", "Blocked"),
        ("unblocked", "Unblocked"),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=10, choices=ENTITY_TYPE_CHOICES)
    entity_id = models.UUIDField(db_index=True)
    
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    reason = models.TextField()
    
    actioned_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name="block_actions"
    )
    actioned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-actioned_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['actioned_at']),
        ]
    
    def __str__(self):
        return f"{self.entity_type} {self.action} at {self.actioned_at}"
