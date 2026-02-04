from django.db import models
from django.core.exceptions import ValidationError
from .base import BaseModel

class Occupancy(BaseModel):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("tenant", "Tenant"),
        ("employee", "Employee"),
        ("contractor", "Contractor"),
        ("family_member", "Family Member"),
        ("guest", "Guest"),
        ("service_provider", "Service Provider"),
    ]
    person = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="occupancies"
    )
    unit = models.ForeignKey(
        "Unit",
        on_delete=models.CASCADE,
        related_name="occupancies"
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    contract_number = models.CharField(max_length=100, blank=True)
    contract_document = models.FileField(upload_to="contracts/", null=True, blank=True)
    monthly_rent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    class Meta:
        ordering = ['-start_date']
        unique_together = ["person", "unit", "role"]
        indexes = [
            models.Index(fields=['person', 'is_active']),
            models.Index(fields=['unit', 'role']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        verbose_name_plural = "Occupancies"
    def __str__(self):
        return f"{self.person} → {self.unit} ({self.get_role_display()})"
    def clean(self):
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date must be before end date")
        existing = Occupancy.objects.filter(
            person=self.person,
            unit=self.unit,
            is_active=True,
            is_deleted=False
        ).exclude(id=self.id)
        if existing.exists():
            raise ValidationError(f"Person is already an occupant in this unit as {existing.first().get_role_display()}")
    @property
    def is_current(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.end_date and today > self.end_date:
            return False
        return today >= self.start_date

class GuestRegistration(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("completed", "Visit Completed"),
    ]
    host = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="hosted_guests"
    )
    guest = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="guest_registrations"
    )
    unit = models.ForeignKey(
        "Unit",
        on_delete=models.CASCADE,
        related_name="guest_registrations"
    )
    expected_arrival = models.DateTimeField()
    expected_departure = models.DateTimeField()
    actual_arrival = models.DateTimeField(null=True, blank=True)
    actual_departure = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_guest_registrations"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    temporary_pin = models.CharField(max_length=10, blank=True, null=True)
    pin_expires_at = models.DateTimeField(null=True, blank=True)
    vehicle = models.ForeignKey(
        "Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_visits"
    )
    class Meta:
        ordering = ['-expected_arrival']
        indexes = [
            models.Index(fields=['host', 'status']),
            models.Index(fields=['guest', 'expected_arrival']),
            models.Index(fields=['status', 'expected_arrival']),
        ]
    def __str__(self):
        return f"{self.guest} visiting {self.host} ({self.status})"
    def clean(self):
        if self.expected_departure <= self.expected_arrival:
            raise ValidationError("Departure must be after arrival")
    @property
    def is_active_visit(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.status == "approved" and
            now >= self.expected_arrival and
            (not self.actual_departure or now <= self.actual_departure)
        )
