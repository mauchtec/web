from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .base import BaseModel


class RuntimeSettings(BaseModel):
    key = models.CharField(max_length=32, unique=True, default="global")
    pin_length = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(4), MaxValueValidator(8)],
    )
    allow_sip_calls = models.BooleanField(default=True)
    anti_passback_enabled = models.BooleanField(default=True)
    anti_passback_window_hours = models.PositiveSmallIntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(72)],
    )
    anti_passback_enforce_no_reentry_without_exit = models.BooleanField(default=True)
    anti_passback_allow_manual_override = models.BooleanField(default=True)
    anti_passback_override_comment_required = models.BooleanField(default=True)
    anti_passback_warning_message = models.CharField(
        max_length=255,
        default="Anti-passback: no valid entry in last 24 hours",
    )
    send_visitor_sms = models.BooleanField(default=True)
    send_visitor_sms_otp = models.BooleanField(default=True)
    send_visitor_sms_exitcode = models.BooleanField(default=True)

    class Meta:
        ordering = ["-modified_at"]
        verbose_name = "Runtime setting"
        verbose_name_plural = "Runtime settings"

    def __str__(self):
        return f"Runtime settings ({self.key})"

    @classmethod
    def default_values(cls):
        return {
            "pin_length": 5,
            "allow_sip_calls": True,
            "anti_passback_enabled": True,
            "anti_passback_window_hours": 24,
            "anti_passback_enforce_no_reentry_without_exit": True,
            "anti_passback_allow_manual_override": True,
            "anti_passback_override_comment_required": True,
            "anti_passback_warning_message": "Anti-passback: no valid entry in last 24 hours",
            "send_visitor_sms": bool(getattr(settings, "SEND_SMS_WITH_PIN_FOR_ADHOC", True)),
            "send_visitor_sms_otp": True,
            "send_visitor_sms_exitcode": True,
        }

    def save(self, *args, **kwargs):
        self.key = "global"
        self.pin_length = max(4, min(int(self.pin_length or 5), 8))
        self.anti_passback_window_hours = max(1, min(int(self.anti_passback_window_hours or 24), 72))
        super().save(*args, **kwargs)

    def as_dict(self):
        return {
            "key": self.key,
            "pin_length": self.pin_length,
            "allow_sip_calls": self.allow_sip_calls,
            "anti_passback_enabled": self.anti_passback_enabled,
            "anti_passback_window_hours": self.anti_passback_window_hours,
            "anti_passback_enforce_no_reentry_without_exit": self.anti_passback_enforce_no_reentry_without_exit,
            "anti_passback_allow_manual_override": self.anti_passback_allow_manual_override,
            "anti_passback_override_comment_required": self.anti_passback_override_comment_required,
            "anti_passback_warning_message": self.anti_passback_warning_message,
            "send_visitor_sms": self.send_visitor_sms,
            "send_visitor_sms_otp": self.send_visitor_sms_otp,
            "send_visitor_sms_exitcode": self.send_visitor_sms_exitcode,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "modified_by": self.modified_by.username if self.modified_by else None,
        }
