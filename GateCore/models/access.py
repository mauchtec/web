import hashlib
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from .base import BaseModel

def validate_schedule_pin(value):
    pin = (value or "").strip()
    if not pin:
        return
    from GateCore.services.runtime_settings import get_pin_length

    pin_length = get_pin_length()
    if len(pin) != pin_length or not pin.isdigit():
        raise ValidationError(f"PIN must be exactly {pin_length} digits.")

class AccessPoint(BaseModel):
    POINT_TYPES = [
        ("gate", "Gate"),
        ("door", "Door"),
        ("lift", "Lift"),
        ("boom", "Boom Gate"),
        ("turnstile", "Turnstile"),
        ("parking", "Parking Gate"),
        ("elevator", "Elevator"),
    ]
    property = models.ForeignKey(
        "Property",
        on_delete=models.CASCADE,
        related_name="access_points"
    )
    unit = models.ForeignKey(
        "Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_points"
    )
    name = models.CharField(max_length=100)
    point_type = models.CharField(max_length=30, choices=POINT_TYPES)
    location_description = models.TextField(blank=True)
    location_coordinates = models.CharField(max_length=100, blank=True)
    requires_authorization = models.BooleanField(default=True)
    default_access = models.CharField(
        max_length=20,
        choices=[("granted", "Granted"), ("denied", "Denied")],
        default="denied"
    )
    is_operational = models.BooleanField(default=True)
    last_maintenance = models.DateField(null=True, blank=True)
    class Meta:
        ordering = ['property', 'name']
        indexes = [
            models.Index(fields=['property', 'point_type']),
            models.Index(fields=['is_operational', 'is_active']),
        ]
    def __str__(self):
        return f"{self.name} ({self.property.name})"

class AccessDevice(BaseModel):
    DEVICE_TYPES = [
        ("rfid", "RFID Reader"),
        ("pin", "PIN Pad"),
        ("biometric", "Biometric Scanner"),
        ("qr", "QR Code Scanner"),
        ("bluetooth", "Bluetooth"),
        ("nfc", "NFC Reader"),
        ("license_plate", "License Plate Reader"),
    ]
    access_point = models.ForeignKey(
        AccessPoint,
        on_delete=models.CASCADE,
        related_name="devices"
    )
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPES)
    name = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, unique=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    config = models.JSONField(default=dict, blank=True)
    class Meta:
        ordering = ['access_point', 'device_type']
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['access_point', 'is_active']),
        ]
    def __str__(self):
        return f"{self.get_device_type_display()} - {self.serial_number}"


class GateTerminal(BaseModel):
    DIRECTION_CHOICES = [
        ("entry", "Entry"),
        ("exit", "Exit"),
        ("both", "Entry & Exit"),
    ]
    DOCKING_MODE_CHOICES = [
        ("local_cloud_platform", "Local Cloud Platform"),
        ("local_software", "Local Software"),
        ("developer", "Developer"),
        ("offline", "Offline"),
    ]
    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("blocked", "Blocked"),
    ]

    serial_number = models.CharField(max_length=120, unique=True)
    display_name = models.CharField(max_length=150)
    manufacturer = models.CharField(max_length=120, blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    site = models.ForeignKey(
        "Site",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gate_terminals",
    )
    access_point = models.ForeignKey(
        "AccessPoint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gate_terminals",
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="entry")
    docking_mode = models.CharField(max_length=32, choices=DOCKING_MODE_CHOICES, default="local_cloud_platform")
    server_url = models.URLField(blank=True)
    server_port = models.PositiveIntegerField(null=True, blank=True)
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default="pending")
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_gate_terminals",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=60, blank=True)
    app_version = models.CharField(max_length=60, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=32, blank=True)
    sync_cursor = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["display_name", "serial_number"]
        indexes = [
            models.Index(fields=["serial_number"]),
            models.Index(fields=["approval_status", "last_seen_at"]),
            models.Index(fields=["site", "direction"]),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.serial_number})"

    @property
    def is_approved(self) -> bool:
        return self.approval_status == "approved"


class DeviceSyncJob(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failure", "Failure"),
    ]

    device_identifier = models.CharField(max_length=200, unique=True)
    device_name = models.CharField(max_length=200, blank=True)
    cursor_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    last_error = models.TextField(blank=True)
    last_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-last_synced_at", "device_identifier"]
        indexes = [
            models.Index(fields=["device_identifier"]),
            models.Index(fields=["last_status", "last_synced_at"]),
        ]

    def __str__(self):
        return f"Device Sync: {self.device_identifier}"

class AccessCredential(BaseModel):
    CREDENTIAL_TYPES = [
        ("card", "RFID Card"),
        ("pin", "PIN Code"),
        ("face", "Face Recognition"),
        ("fingerprint", "Fingerprint"),
        ("mobile", "Mobile App"),
        ("sticker", "Vehicle Sticker"),
        ("qr", "QR Code"),
        ("biometric", "Biometric"),
    ]
    person = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="credentials"
    )
    credential_type = models.CharField(max_length=30, choices=CREDENTIAL_TYPES)
    credential_value = models.CharField(max_length=255)
    hashed_value = models.CharField(max_length=255, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_temporary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    class Meta:
        ordering = ['person', '-issued_at']
        indexes = [
            models.Index(fields=['person', 'credential_type']),
            models.Index(fields=['hashed_value']),
            models.Index(fields=['expires_at', 'is_active']),
        ]
    def __str__(self):
        return f"{self.get_credential_type_display()} for {self.person}"
    def save(self, *args, **kwargs):
        if self.credential_type in ["pin", "card", "mobile"] and self.credential_value:
            self.hashed_value = hashlib.sha256(self.credential_value.encode()).hexdigest()
        super().save(*args, **kwargs)
    def verify_credential(self, input_value):
        if self.credential_type in ["pin", "card", "mobile"]:
            return hashlib.sha256(input_value.encode()).hexdigest() == self.hashed_value
        return input_value == self.credential_value

class ScheduleRule(BaseModel):
    RECUR_CHOICES = [
        ('none', 'No Repeat'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    recur_type = models.CharField(max_length=20, choices=RECUR_CHOICES, default='none')
    recur_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_schedules')
    modified_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_schedules')
    modified_at = models.DateTimeField(auto_now=True)
    SCHEDULE_TYPES = [
        ("24x7", "24/7 Access"),
        ("business_hours", "Business Hours"),
        ("custom", "Custom Schedule"),
        ("weekdays", "Weekdays Only"),
        ("weekends", "Weekends Only"),
    ]

    TYPE_CHOICES = [
        ('preclearance', 'Preclearance'),
        ('schedule', 'Schedule'),
    ]

    REASON_CHOICES = [
        ('guest', 'Guest'),
        ('delivery', 'Delivery'),
        ('maintenance', 'Maintenance'),
        ('contractor', 'Contractor'),
        ('family', 'Family'),
        ('other', 'Other'),
    ]

    DAYS_CHOICES = [
        ('weekdays', 'Weekdays'),
        ('workdays', 'Workdays'),
        ('weekends', 'Weekends'),
        ('custom', 'Custom'),
    ]

    name = models.CharField(max_length=100)
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True, blank=True)
    visitor = models.ForeignKey('Person', on_delete=models.SET_NULL, null=True, blank=True)
    schedule_type = models.CharField(max_length=30, choices=SCHEDULE_TYPES, default="custom")
    schedule_kind = models.CharField(max_length=20, choices=TYPE_CHOICES, default='schedule')
    start_time = models.TimeField(default="00:00")
    end_time = models.TimeField(default="23:59")
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='guest')
    reason_other = models.CharField(max_length=100, blank=True)
    visitor_full_name = models.CharField(max_length=100, blank=True)
    visitor_email = models.EmailField(blank=True)
    visitor_mobile = models.CharField(max_length=20, blank=True)
    pin = models.CharField(max_length=10, blank=True, validators=[validate_schedule_pin])
    valid_from = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    days_allowed = models.CharField(max_length=20, choices=DAYS_CHOICES, default='weekdays')
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=True)
    sunday = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    exclude_holidays = models.BooleanField(default=True)
    notify_resident = models.BooleanField(default=False)
    preclearance_entry_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def is_allowed_now(self):
        from django.utils import timezone
        now = timezone.now()
        if self.valid_until and now.date() > self.valid_until:
            return False
        if now.date() < self.valid_from:
            return False
        weekday = now.weekday()
        days = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
        if not days[weekday]:
            return False
        if not (self.start_time <= now.time() <= self.end_time):
            return False
        return True

    def save(self, *args, **kwargs):
        original_pin = None
        if self.pk:
            original_pin = type(self).objects.filter(pk=self.pk).values_list("pin", flat=True).first()
        if self.schedule_kind == 'preclearance':
            if not self.valid_from:
                self.valid_from = timezone.now().date()
            self.valid_until = self.valid_from + timedelta(days=1)
            self.recur_type = 'none'

        if not self.pin:
            from GateCore.services.pin_generator import generate_unique_pin
            try:
                self.pin = generate_unique_pin()
            except RuntimeError:
                pass  # leave empty if no unique PIN available (very rare)
        self.pin = (self.pin or "").strip()
        if self.pin and self.pin != original_pin:
            validate_schedule_pin(self.pin)
        if original_pin == self.pin and self.pk:
            self.full_clean(exclude=["pin"])
        else:
            self.full_clean()
        super().save(*args, **kwargs)


class SystemPreclearanceConfig(BaseModel):
    key = models.CharField(max_length=50, unique=True, default="system-preclearance")
    schedule_rule = models.OneToOneField(
        ScheduleRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_preclearance_config"
    )
    qr_base64 = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    trigger_payload = models.JSONField(default=dict, blank=True)
    last_rotated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_rotated']

    def __str__(self):
        return f"System Preclearance ({self.key})"


class SMSDeliveryLog(BaseModel):
    STATUS_CHOICES = [
        ("attempt", "Attempt"),
        ("success", "Success"),
        ("failure", "Failure"),
    ]

    trigger = models.CharField(max_length=80, blank=True)
    provider = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="attempt")
    recipient_phone = models.CharField(max_length=30, blank=True)
    recipient_name = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    provider_message_id = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    unit = models.ForeignKey(
        "Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_delivery_logs",
    )
    person = models.ForeignKey(
        "Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_delivery_logs",
    )
    visitor_name = models.CharField(max_length=120, blank=True)
    visitor_phone = models.CharField(max_length=30, blank=True)
    schedule_rule = models.ForeignKey(
        "ScheduleRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_delivery_logs",
    )
    context_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["provider", "created_at"]),
            models.Index(fields=["recipient_phone"]),
            models.Index(fields=["trigger"]),
        ]

    def __str__(self):
        return f"{self.provider or 'sms'}:{self.status}:{self.recipient_phone}"


class AccessPermission(BaseModel):
    person = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="permissions"
    )
    access_point = models.ForeignKey(
        AccessPoint,
        on_delete=models.CASCADE,
        related_name="permissions"
    )
    schedule_rule = models.ForeignKey(
        ScheduleRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permissions"
    )
    schedule_override = models.JSONField(default=dict, blank=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_daily_uses = models.IntegerField(default=0)
    current_daily_uses = models.IntegerField(default=0)
    last_reset = models.DateField(auto_now_add=True)
    priority = models.IntegerField(default=1)
    class Meta:
        ordering = ['-priority', 'person']
        unique_together = ["person", "access_point"]
        indexes = [
            models.Index(fields=['person', 'is_active']),
            models.Index(fields=['access_point', 'valid_until']),
            models.Index(fields=['valid_until', 'is_active']),
        ]
    def __str__(self):
        return f"{self.person} → {self.access_point}"
    @property
    def is_valid_now(self):
        from django.utils import timezone
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.schedule_rule:
            return self.schedule_rule.is_allowed_now()
        return True
    def can_access(self):
        if not self.is_valid_now:
            return False
        from django.utils import timezone
        if self.max_daily_uses > 0:
            today = timezone.now().date()
            if self.last_reset != today:
                self.current_daily_uses = 0
                self.last_reset = today
                self.save(update_fields=['current_daily_uses', 'last_reset'])
            if self.current_daily_uses >= self.max_daily_uses:
                return False
        return True
    def record_access(self):
        if self.max_daily_uses > 0:
            self.current_daily_uses += 1
            self.save(update_fields=['current_daily_uses'])

class AccessLog(BaseModel):
    RESULT_CHOICES = [
        ("granted", "Granted"),
        ("denied", "Denied"),
        ("expired", "Expired"),
        ("invalid", "Invalid Credential"),
        ("scheduled", "Outside Schedule"),
        ("limit", "Daily Limit Exceeded"),
        ("blacklisted", "Blacklisted"),
        ("error", "System Error"),
    ]
    person = models.ForeignKey(
        "Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs"
    )
    device = models.ForeignKey(
        AccessDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    access_point = models.ForeignKey(
        AccessPoint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    credential = models.ForeignKey(
        AccessCredential,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    timestamp = models.DateTimeField(default=timezone.now)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    reason = models.CharField(max_length=100, blank=True)
    credential_value_used = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    raw_scan_data = models.JSONField(default=dict, blank=True)
    driver_photo = models.FileField(upload_to="access_logs/driver/", null=True, blank=True)
    vehicle_photo = models.FileField(upload_to="access_logs/vehicle/", null=True, blank=True)
    barcode_hex = models.TextField(blank=True)
    scan_timestamp = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['person', 'timestamp']),
            models.Index(fields=['result', 'timestamp']),
            models.Index(fields=['device', 'timestamp']),
        ]
    def __str__(self):
        return f"{self.timestamp} - {self.person or 'Unknown'} - {self.get_result_display()}"

class Blacklist(BaseModel):
    TARGET_TYPES = [
        ("person", "Person"),
        ("vehicle", "Vehicle"),
        ("credential", "Credential"),
        ("ip_address", "IP Address"),
    ]
    REASON_CHOICES = [
        ("security", "Security Concern"),
        ("payment", "Payment Issues"),
        ("behavior", "Inappropriate Behavior"),
        ("lost", "Lost Card/Credential"),
        ("expired", "Contract Expired"),
        ("other", "Other"),
    ]
    target_type = models.CharField(max_length=20, choices=TARGET_TYPES)
    person = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="blacklist_entries"
    )
    vehicle = models.ForeignKey(
        "Vehicle",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    credential = models.ForeignKey(
        AccessCredential,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    details = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    blacklisted_from = models.DateTimeField(default=timezone.now)
    blacklisted_until = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-blacklisted_from']
        indexes = [
            models.Index(fields=['target_type']),
            models.Index(fields=['blacklisted_until']),
        ]
    def __str__(self):
        if self.person:
            return f"Blacklisted: {self.person}"
        elif self.vehicle:
            return f"Blacklisted: {self.vehicle}"
        elif self.credential:
            return f"Blacklisted: {self.credential}"
        else:
            return f"Blacklisted: {self.target_type}"
    @property
    def is_currently_active(self):
        from django.utils import timezone
        if self.blacklisted_until and timezone.now() > self.blacklisted_until:
            return False
        return super().is_active and not self.is_deleted
