import uuid
import hashlib
from django.db import models
from .base import BaseModel


class RawScanArchive(models.Model):
    """Immutable storage for original scanned documents"""
    DOCUMENT_TYPES = (
        ("driving_license", "Driving License"),
        ("vehicle_disk", "Vehicle Registration Disk"),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    source_device = models.CharField(max_length=100)
    scan_time = models.DateTimeField(auto_now_add=True)
    
    raw_json = models.JSONField()  # original untouched scan
    sha256_hash = models.CharField(max_length=64, db_index=True)
    
    processed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-scan_time']
        indexes = [
            models.Index(fields=['document_type', 'scan_time']),
            models.Index(fields=['sha256_hash']),
        ]
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.scan_time}"
    
    def save(self, *args, **kwargs):
        # Auto-generate SHA256 hash from raw_json if not provided
        if not self.sha256_hash and self.raw_json:
            import json
            json_str = json.dumps(self.raw_json, sort_keys=True)
            self.sha256_hash = hashlib.sha256(json_str.encode()).hexdigest()
        super().save(*args, **kwargs)


class DriverLicense(BaseModel):
    """Driver license with expiry tracking and status management"""
    STATUS_CHOICES = (
        ("valid", "Valid"),
        ("expired", "Expired"),
        ("blocked", "Blocked"),
    )
    
    person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        related_name="licenses"
    )
    
    license_number = models.CharField(max_length=50, unique=True, db_index=True)
    issue_date = models.DateField()
    expiry_date = models.DateField(db_index=True)
    
    # Using JSONField for compatibility with SQLite
    # Can be migrated to PostgreSQL ArrayField when needed
    vehicle_codes = models.JSONField(default=list, blank=True)
    vehicle_restrictions = models.JSONField(default=list, blank=True)
    license_code_issue_dates = models.JSONField(default=list, blank=True)
    
    driver_restriction_codes = models.CharField(max_length=10, blank=True)
    prdp_codes = models.JSONField(default=list, blank=True)
    prdp_expiry_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="valid")
    
    raw_scan = models.ForeignKey(
        RawScanArchive,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_licenses"
    )
    
    class Meta:
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['person', 'status']),
            models.Index(fields=['expiry_date', 'status']),
            models.Index(fields=['license_number']),
        ]
    
    def __str__(self):
        return f"{self.license_number} - {self.person}"


class VehicleRegistration(BaseModel):
    """Vehicle registration disk with expiry tracking"""
    STATUS_CHOICES = (
        ("valid", "Valid"),
        ("expired", "Expired"),
        ("blocked", "Blocked"),
    )
    
    vehicle = models.ForeignKey(
        'Vehicle',
        on_delete=models.CASCADE,
        related_name="registrations"
    )
    
    plate_number = models.CharField(max_length=20, db_index=True)
    vehicle_register_number = models.CharField(max_length=20, blank=True)
    disk_number = models.CharField(max_length=50, unique=True)
    
    expiry_date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="valid")
    
    raw_scan = models.ForeignKey(
        RawScanArchive,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_registrations"
    )
    
    class Meta:
        ordering = ['-expiry_date']
        indexes = [
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['plate_number']),
            models.Index(fields=['disk_number']),
            models.Index(fields=['expiry_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.plate_number} - {self.disk_number}"
