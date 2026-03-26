from django.core.exceptions import ValidationError

from GateCore.models.runtime_settings import RuntimeSettings


VISITOR_SMS_TRIGGERS = {
    "entry_workflow_sms",
    "mobile_login_otp",
    "preclearance_entry_pin",
    "visitor_exitcode",
    "exitcode",
}


def get_runtime_settings() -> RuntimeSettings:
    obj, _ = RuntimeSettings.objects.get_or_create(
        key="global",
        defaults=RuntimeSettings.default_values(),
    )
    return obj


def get_pin_length() -> int:
    return max(4, min(int(get_runtime_settings().pin_length or 5), 8))


def allow_sip_calls() -> bool:
    return bool(get_runtime_settings().allow_sip_calls)


def get_antipassback_config() -> dict:
    settings_obj = get_runtime_settings()
    return {
        "enabled": bool(settings_obj.anti_passback_enabled),
        "window_hours": max(1, min(int(settings_obj.anti_passback_window_hours or 24), 72)),
        "enforce_no_reentry_without_exit": bool(settings_obj.anti_passback_enforce_no_reentry_without_exit),
        "allow_manual_override": bool(settings_obj.anti_passback_allow_manual_override),
        "override_comment_required": bool(settings_obj.anti_passback_override_comment_required),
        "warning_message": (settings_obj.anti_passback_warning_message or "").strip()
        or "Anti-passback: no valid entry in last 24 hours",
    }


def should_send_visitor_sms(trigger: str | None = None) -> bool:
    settings_obj = get_runtime_settings()
    trigger = (trigger or "").strip().lower()
    if trigger in {"mobile_login_otp", "otp"}:
        return bool(settings_obj.send_visitor_sms and settings_obj.send_visitor_sms_otp)
    if trigger in {"visitor_exitcode", "exitcode"}:
        return bool(settings_obj.send_visitor_sms and settings_obj.send_visitor_sms_exitcode)
    if trigger in VISITOR_SMS_TRIGGERS:
        return bool(settings_obj.send_visitor_sms)
    return True


def runtime_settings_payload(obj: RuntimeSettings | None = None) -> dict:
    obj = obj or get_runtime_settings()
    return obj.as_dict()


def update_runtime_settings(*, modified_by=None, **updates) -> RuntimeSettings:
    obj = get_runtime_settings()
    for field in (
        "pin_length",
        "allow_sip_calls",
        "anti_passback_enabled",
        "anti_passback_window_hours",
        "anti_passback_enforce_no_reentry_without_exit",
        "anti_passback_allow_manual_override",
        "anti_passback_override_comment_required",
        "anti_passback_warning_message",
        "send_visitor_sms",
        "send_visitor_sms_otp",
        "send_visitor_sms_exitcode",
    ):
        if field in updates and updates[field] is not None:
            setattr(obj, field, updates[field])
    if modified_by is not None:
        obj.modified_by = modified_by
    try:
        obj.full_clean()
        obj.save()
    except ValidationError:
        raise
    return obj
