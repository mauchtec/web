import hashlib
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from .base import BaseModel

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
    pin = models.CharField(max_length=10, blank=True)
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
        if not self.pin:
            import random
            for _ in range(10):
                candidate = str(random.randint(10000, 99999))
                if not ScheduleRule.objects.filter(pin=candidate).exists():
                    self.pin = candidate
                    break
        super().save(*args, **kwargs)

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
