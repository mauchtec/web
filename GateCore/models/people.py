import re
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import validate_email
from .base import BaseModel

def validate_phone_number(value):
    if not re.match(r'^\+?1?\d{9,15}$', value):
        raise ValidationError("Enter a valid phone number (9-15 digits, optional + prefix)")


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
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    id_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    phone = models.CharField(max_length=30, validators=[validate_phone_number])
    phone_device_type = models.CharField(max_length=20, choices=PHONE_DEVICE_CHOICES, blank=True)
    phone_otp = models.CharField(max_length=8, blank=True)
    phone_otp_created = models.DateTimeField(null=True, blank=True)
    facial_recognition_enabled = models.BooleanField(default=False)
    email = models.EmailField(blank=True, null=True, validators=[validate_email])
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    photo = models.ImageField(upload_to="people/", blank=True, null=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    # Blocking support
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['id_number']),
            models.Index(fields=['is_active', 'is_deleted']),
        ]
        verbose_name_plural = "People"
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def surname(self):
        """Alias for last_name to match driver license structure"""
        return self.last_name
    
    @surname.setter
    def surname(self, value):
        self.last_name = value
    
    @property
    def initials(self):
        """Generate initials from first name and middle name"""
        parts = []
        if self.first_name:
            parts.append(self.first_name[0].upper())
        if self.middle_name:
            parts.append(self.middle_name[0].upper())
        return ''.join(parts)
    
    @property
    def birthdate(self):
        """Alias for date_of_birth to match driver license structure"""
        return self.date_of_birth
    
    @birthdate.setter
    def birthdate(self, value):
        self.date_of_birth = value
    
    def clean(self):
        if self.email and Person.objects.filter(email=self.email).exclude(id=self.id).exists():
            raise ValidationError({"email": "A person with this email already exists."})

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
    
    # Vehicle Identity (VIN-based)
    vin = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    engine_number = models.CharField(max_length=50, blank=True)
    
    # Keep license_plate for backward compatibility
    license_plate = models.CharField(max_length=20)
    
    vehicle_type = models.CharField(max_length=30, choices=VEHICLE_TYPES, default="car", blank=True)
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=30, blank=True)
    year = models.IntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPES, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    registration_expiry = models.DateField(null=True, blank=True)
    has_sticker = models.BooleanField(default=False)
    sticker_number = models.CharField(max_length=50, blank=True)
    
    # Blocking support
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True)
    
    @property
    def colour(self):
        """Alias for color (British spelling)"""
        return self.color
    
    @colour.setter
    def colour(self, value):
        self.color = value
    
    class Meta:
        ordering = ['license_plate']
        unique_together = ["license_plate", "person"]
        indexes = [
            models.Index(fields=['license_plate']),
            models.Index(fields=['person', 'is_active']),
            models.Index(fields=['vin']),
            models.Index(fields=['is_blocked', 'is_active']),
        ]
    def __str__(self):
        return f"{self.license_plate} ({self.person})"


class DriverVehicleAssociation(BaseModel):
    """Tracks driver-vehicle pairings over time"""
    
    person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        related_name="driver_vehicle_associations"
    )
    vehicle = models.ForeignKey(
        'Vehicle',
        on_delete=models.CASCADE,
        related_name="driver_associations"
    )
    
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    total_visits = models.IntegerField(default=0)
    
    is_primary_driver = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('person', 'vehicle')
        indexes = [
            models.Index(fields=['person', 'last_seen']),
            models.Index(fields=['vehicle', 'last_seen']),
            models.Index(fields=['is_primary_driver']),
        ]
    
    def __str__(self):
        return f"{self.person} - {self.vehicle}"
