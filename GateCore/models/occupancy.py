from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

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
        now = timezone.now()
        return (
            self.status == "approved" and
            now >= self.expected_arrival and
            (not self.actual_departure or now <= self.actual_departure)
        )


class VisitorFaceAccessGrant(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("completed", "Completed"),
        ("revoked", "Revoked"),
    ]

    guest_registration = models.ForeignKey(
        "GuestRegistration",
        on_delete=models.CASCADE,
        related_name="face_access_grants",
    )
    person = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="visitor_face_access_grants",
    )
    entry_terminal = models.ForeignKey(
        "GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitor_entry_face_grants",
    )
    exit_terminal = models.ForeignKey(
        "GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitor_exit_face_grants",
    )
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    entry_pass_used = models.BooleanField(default=False)
    exit_pass_used = models.BooleanField(default=False)
    entry_used_at = models.DateTimeField(null=True, blank=True)
    exit_used_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    revoked_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "valid_until"]),
            models.Index(fields=["person", "status"]),
            models.Index(fields=["guest_registration", "status"]),
        ]

    def __str__(self):
        return f"{self.person} visitor face grant ({self.status})"

    def clean(self):
        if self.valid_until <= self.valid_from:
            raise ValidationError("valid_until must be after valid_from")
        if self.entry_terminal and self.entry_terminal.direction != "entry":
            raise ValidationError({"entry_terminal": "Entry terminal must have direction 'entry'."})
        if self.exit_terminal and self.exit_terminal.direction != "exit":
            raise ValidationError({"exit_terminal": "Exit terminal must have direction 'exit'."})
        if self.guest_registration_id and self.person_id and self.guest_registration.guest_id != self.person_id:
            raise ValidationError({"person": "Grant person must match the guest registration guest."})

    @property
    def is_active_grant(self) -> bool:
        now = timezone.now()
        return self.status in {"approved", "active"} and self.valid_from <= now <= self.valid_until

    @property
    def is_fully_consumed(self) -> bool:
        entry_done = not self.entry_terminal_id or self.entry_pass_used
        exit_done = not self.exit_terminal_id or self.exit_pass_used
        return entry_done and exit_done

    @classmethod
    def default_valid_window(cls):
        now = timezone.now()
        return now, now + timedelta(hours=24)

    @classmethod
    def resolve_terminals_for_guest_registration(cls, guest_registration):
        unit = getattr(guest_registration, "unit", None)
        property_obj = getattr(unit, "property", None) if unit else None
        site = getattr(property_obj, "site", None) if property_obj else None

        from .access import GateTerminal

        terminals = GateTerminal.objects.filter(
            approval_status="approved",
            direction__in=("entry", "exit"),
        )
        if site:
            site_terminals = terminals.filter(site=site)
            if site_terminals.exists():
                terminals = site_terminals

        entry_terminal = terminals.filter(direction="entry").order_by("display_name", "serial_number").first()
        exit_terminal = terminals.filter(direction="exit").order_by("display_name", "serial_number").first()
        return entry_terminal, exit_terminal

    @classmethod
    def create_for_guest_registration(cls, guest_registration, *, notes: str = ""):
        valid_from, valid_until = cls.default_valid_window()
        entry_terminal, exit_terminal = cls.resolve_terminals_for_guest_registration(guest_registration)
        return cls.objects.create(
            guest_registration=guest_registration,
            person=guest_registration.guest,
            entry_terminal=entry_terminal,
            exit_terminal=exit_terminal,
            valid_from=valid_from,
            valid_until=valid_until,
            status="pending",
            notes=notes,
        )
