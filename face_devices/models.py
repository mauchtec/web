from django.conf import settings
from django.db import models
from django.utils import timezone

from GateCore.models.base import BaseModel


class FaceDeviceEvent(BaseModel):
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]
    STATUS_CHOICES = [
        ("received", "Received"),
        ("sent", "Sent"),
        ("success", "Success"),
        ("error", "Error"),
    ]

    terminal = models.ForeignKey(
        "GateCore.GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_events",
    )
    device_identifier = models.CharField(max_length=200, db_index=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    command = models.CharField(max_length=120, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="received")
    payload = models.JSONField(default=dict, blank=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    event_time = models.DateTimeField(auto_now_add=True, db_index=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-event_time", "-created_at"]
        indexes = [
            models.Index(fields=["device_identifier", "event_time"]),
            models.Index(fields=["command", "event_time"]),
            models.Index(fields=["status", "event_time"]),
        ]

    def __str__(self):
        return f"{self.device_identifier}:{self.direction}:{self.command}"


class FaceDeviceAction(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("error", "Error"),
        ("timeout", "Timeout"),
    ]

    ACTION_CHOICES = [
        ("ping", "Ping"),
        ("pull_settings", "Pull Settings"),
        ("pull_user_count", "Pull User Count"),
        ("pull_user_ids", "Pull User IDs"),
        ("pull_groups", "Pull Groups"),
        ("pull_access_logs", "Pull Access Logs"),
        ("sync_users", "Sync Users"),
        ("add_user", "Add User"),
        ("edit_user", "Edit User"),
        ("create_group", "Create Group"),
        ("delete_group", "Delete Group"),
        ("delete_user", "Delete User"),
        ("delete_all_users", "Delete All Users"),
        ("open_door", "Open Door"),
        ("reboot", "Reboot Device"),
    ]

    terminal = models.ForeignKey(
        "GateCore.GateTerminal",
        on_delete=models.CASCADE,
        related_name="face_device_actions",
    )
    device_identifier = models.CharField(max_length=200, db_index=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_actions_requested",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("can_run_destructive_face_device_actions", "Can run destructive face device actions"),
        ]
        indexes = [
            models.Index(fields=["device_identifier", "created_at"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.device_identifier}:{self.action}:{self.status}"


class FaceDeviceRemoteChallenge(BaseModel):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("consumed", "Consumed"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    terminal = models.ForeignKey(
        "GateCore.GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_remote_challenges",
    )
    device_identifier = models.CharField(max_length=200, db_index=True)
    nonce = models.CharField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    estate_id = models.CharField(max_length=40, blank=True)
    platform_id = models.CharField(max_length=40, blank=True)
    estate_name = models.CharField(max_length=255, blank=True)
    challenge_payload = models.JSONField(default=dict, blank=True)
    issued_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_remote_challenges_consumed",
    )

    class Meta:
        ordering = ["-issued_at", "-created_at"]
        indexes = [
            models.Index(fields=["device_identifier", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"{self.device_identifier}:{self.status}:{self.nonce}"


class FaceDeviceAccessLog(BaseModel):
    RESULT_CHOICES = [
        ("pass", "Pass"),
        ("deny", "Deny"),
        ("unknown", "Unknown"),
    ]

    terminal = models.ForeignKey(
        "GateCore.GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_access_logs",
    )
    person = models.ForeignKey(
        "GateCore.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_access_logs",
    )
    device_identifier = models.CharField(max_length=200, db_index=True)
    source_command = models.CharField(max_length=120, blank=True, db_index=True)
    event_time = models.DateTimeField(default=timezone.now, db_index=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default="unknown", db_index=True)
    confidence = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    snapshot_image = models.ImageField(upload_to="face_devices/snapshots/", blank=True, null=True)
    panoramic_image = models.ImageField(upload_to="face_devices/panoramic/", blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-event_time", "-created_at"]
        indexes = [
            models.Index(fields=["device_identifier", "event_time"]),
            models.Index(fields=["result", "event_time"]),
            models.Index(fields=["source_command", "event_time"]),
        ]

    def __str__(self):
        return f"{self.device_identifier}:{self.result}:{self.event_time.isoformat() if self.event_time else ''}"


class FaceDeviceUserState(BaseModel):
    STATE_CHOICES = [
        ("present", "Present On Device"),
        ("missing", "Missing On Device"),
        ("unexpected", "Unexpected On Device"),
        ("stale", "Stale"),
    ]

    terminal = models.ForeignKey(
        "GateCore.GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_user_states",
    )
    person = models.ForeignKey(
        "GateCore.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_user_states",
    )
    device_identifier = models.CharField(max_length=200, db_index=True)
    user_identifier = models.CharField(max_length=200, db_index=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, db_index=True)
    last_seen_on_device_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["user_identifier"]
        constraints = [
            models.UniqueConstraint(
                fields=["device_identifier", "user_identifier"],
                name="face_device_user_state_unique_device_user",
            )
        ]
        indexes = [
            models.Index(fields=["device_identifier", "state"]),
            models.Index(fields=["user_identifier", "state"]),
        ]

    def __str__(self):
        return f"{self.device_identifier}:{self.user_identifier}:{self.state}"


class FaceDeviceStrangerEvent(BaseModel):
    STATUS_CHOICES = [
        ("new", "New"),
        ("reviewed", "Reviewed"),
        ("dismissed", "Dismissed"),
        ("promoted", "Promoted To Person"),
    ]

    terminal = models.ForeignKey(
        "GateCore.GateTerminal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_device_stranger_events",
    )
    access_log = models.OneToOneField(
        FaceDeviceAccessLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stranger_event",
    )
    promoted_person = models.ForeignKey(
        "GateCore.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promoted_face_device_stranger_events",
    )
    device_identifier = models.CharField(max_length=200, db_index=True)
    source_command = models.CharField(max_length=120, blank=True, db_index=True)
    event_time = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    confidence = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    liveness_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    credential_type = models.CharField(max_length=40, blank=True, db_index=True)
    credential_value = models.CharField(max_length=200, blank=True, db_index=True)
    face_group_name = models.CharField(max_length=120, blank=True)
    snapshot_image = models.ImageField(upload_to="face_devices/strangers/snapshots/", blank=True, null=True)
    panoramic_image = models.ImageField(upload_to="face_devices/strangers/panoramic/", blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_face_device_stranger_events",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-event_time", "-created_at"]
        indexes = [
            models.Index(fields=["device_identifier", "event_time"]),
            models.Index(fields=["status", "event_time"]),
            models.Index(fields=["credential_type", "credential_value"]),
        ]

    def __str__(self):
        return f"{self.device_identifier}:{self.status}:{self.event_time.isoformat() if self.event_time else ''}"
