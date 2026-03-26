from django.db import models
from .base import BaseModel


class FaceReference(BaseModel):
    """Stores versioned face reference images for a person.
    The original enrollment image is never deleted."""

    ROLE_CHOICES = [
        ("primary", "Primary (enrollment)"),
        ("verified", "Verified update"),
        ("pending", "Pending review"),
    ]

    person = models.ForeignKey(
        "GateCore.Person",
        on_delete=models.CASCADE,
        related_name="face_references",
    )
    image = models.ImageField(upload_to="people/face_references/")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="primary")
    compreface_image_id = models.CharField(max_length=120, blank=True)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    similarity_to_primary = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"FaceRef {self.role} for {self.person_id} ({self.created_at})"


class FaceVerificationLog(BaseModel):
    """Logs every face comparison attempt for audit purposes."""

    ACTION_CHOICES = [
        ("enroll", "Initial enrollment"),
        ("update_face", "Face update attempt"),
        ("admin_review", "Admin review"),
        ("admin_reset", "Admin reset"),
    ]

    RESULT_CHOICES = [
        ("approved", "Approved"),
        ("needs_review", "Needs review"),
        ("rejected", "Rejected"),
        ("error", "Error"),
    ]

    person = models.ForeignKey(
        "GateCore.Person",
        on_delete=models.CASCADE,
        related_name="face_verification_logs",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    similarity_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    device_info = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True)

    # Link to the face reference that was created/reviewed (if any)
    face_reference = models.ForeignKey(
        FaceReference,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_logs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.result} for {self.person_id} ({self.similarity_score}%)"
