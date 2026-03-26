import re
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import validate_email
from .base import BaseModel

def validate_phone_number(value):
    raw = str(value or "").strip()
    # Allow short internal PBX extensions such as 1001/1002 alongside normal phone numbers.
    if re.fullmatch(r"\d{3,5}", raw):
        return
    # Accept common user inputs (065..., 0027..., +27..., digits) and normalize in Person.clean().
    if not re.match(r'^[+\d][\d\s\-()]{8,25}$', raw):
        raise ValidationError("Enter a valid phone number.")


class Person(BaseModel):
    PHONE_DEVICE_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("feature", "Feature Phone"),
        ("other", "Other"),
    ]

    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
        ("U", "Prefer not to say"),
    ]
    FACE_ENROLLMENT_STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("synced", "Synced"),
        ("disabled", "Disabled"),
    ]
    PHOTO_REVIEW_STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    id_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    card_number = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, validators=[validate_phone_number], unique=True)
    device_identifier = models.CharField(max_length=200, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="person_profile"
    )
    phone_device_type = models.CharField(max_length=20, choices=PHONE_DEVICE_CHOICES, blank=True)
    phone_otp = models.CharField(max_length=8, blank=True)
    phone_otp_created = models.DateTimeField(null=True, blank=True)
    device_name = models.CharField(max_length=200, blank=True)
    device_model = models.CharField(max_length=200, blank=True)
    device_serial_number = models.CharField(max_length=200, blank=True)
    device_os = models.CharField(max_length=50, blank=True)
    device_app_version = models.CharField(max_length=50, blank=True)
    device_info = models.JSONField(default=dict, blank=True)
    facial_recognition_enabled = models.BooleanField(default=False)
    face_provider = models.CharField(max_length=30, blank=True, default="compreface")
    face_subject_id = models.CharField(max_length=120, blank=True)
    face_enrollment_status = models.CharField(
        max_length=20,
        choices=FACE_ENROLLMENT_STATUS_CHOICES,
        default="not_started",
    )
    face_enrollment_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_enrolled_at = models.DateTimeField(null=True, blank=True)
    face_last_synced_at = models.DateTimeField(null=True, blank=True)
    face_enrollment_error = models.TextField(blank=True)
    face_reference_image_id = models.CharField(max_length=120, blank=True)
    face_user_type = models.PositiveIntegerField(null=True, blank=True)
    face_access_password = models.CharField(max_length=120, blank=True)
    face_pass_rule_id = models.CharField(max_length=120, blank=True)
    face_tts_name = models.CharField(max_length=200, blank=True)
    face_effective_from = models.DateTimeField(null=True, blank=True)
    face_max_pass_count = models.PositiveIntegerField(null=True, blank=True)
    face_pass_count_cycle = models.PositiveIntegerField(null=True, blank=True)
    photo_review_status = models.CharField(
        max_length=20,
        choices=PHOTO_REVIEW_STATUS_CHOICES,
        default="not_started",
    )
    photo_similarity_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    photo_reviewed_at = models.DateTimeField(null=True, blank=True)
    photo_review_error = models.TextField(blank=True)
    email = models.EmailField(blank=True, null=True, validators=[validate_email])
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    access_expires_on = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="people/", blank=True, null=True)
    photo_review_attempt = models.ImageField(upload_to="people/photo_reviews/", blank=True, null=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['id_number']),
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['phone']),
        ]
        verbose_name_plural = "People"
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    def clean(self):
        from GateCore.services.mobile_auth import normalize_phone

        normalized = normalize_phone(self.phone)
        if not normalized:
            raise ValidationError({"phone": "Enter a valid phone number."})
        self.phone = normalized

        if self.email and Person.objects.filter(email=self.email).exclude(id=self.id).exists():
            raise ValidationError({"email": "A person with this email already exists."})

        if Person.objects.filter(phone=self.phone).exclude(id=self.id).exists():
            raise ValidationError({"phone": "A person with this phone number already exists."})

    def save(self, *args, **kwargs):
        # Ensure consistent storage and unique constraint behavior.
        self.full_clean()
        return super().save(*args, **kwargs)

class Vehicle(BaseModel):
    VEHICLE_TYPES = [
        ("car", "Car"),
        ("motorcycle", "Motorcycle"),
        ("truck", "Truck"),
        ("van", "Van"),
        ("bus", "Bus"),
        ("bicycle", "Bicycle"),
    ]
    FUEL_TYPES = [
        ("petrol", "Petrol"),
        ("diesel", "Diesel"),
        ("electric", "Electric"),
        ("hybrid", "Hybrid"),
        ("cng", "CNG"),
    ]
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="vehicles"
    )
    license_plate = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=30, choices=VEHICLE_TYPES, default="car")
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=30, blank=True)
    year = models.IntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPES, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    registration_expiry = models.DateField(null=True, blank=True)
    has_sticker = models.BooleanField(default=False)
    sticker_number = models.CharField(max_length=50, blank=True)
    class Meta:
        ordering = ['license_plate']
        unique_together = ["license_plate", "person"]
        indexes = [
            models.Index(fields=['license_plate']),
            models.Index(fields=['person', 'is_active']),
        ]
    def __str__(self):
        return f"{self.license_plate} ({self.person})"
