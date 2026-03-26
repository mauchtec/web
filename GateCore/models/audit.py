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
        ("face_enroll", "Enroll Face"),
        ("face_enroll_failed", "Face Enrollment Failed"),
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
