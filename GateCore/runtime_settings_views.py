import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from GateCore.services.runtime_settings import (
    runtime_settings_payload,
    update_runtime_settings,
)


def _is_staff(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_payload(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            body = request.body.decode("utf-8").strip()
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            return None
    data = request.POST.dict()
    if data:
        return data
    try:
        body = request.body.decode("utf-8").strip()
        return json.loads(body) if body else {}
    except Exception:
        return {}


@login_required
def runtime_settings_page(request):
    if not _is_staff(request.user):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return render(
        request,
        "frontend/gatecore_runtime_settings.html",
        {"runtime_settings": runtime_settings_payload()},
    )


@login_required
@require_http_methods(["GET", "POST", "PATCH"])
def runtime_settings_api(request):
    if not _is_staff(request.user):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    if request.method == "GET":
        return JsonResponse({"success": True, "settings": runtime_settings_payload()})

    data = _parse_payload(request)
    if data is None:
        return JsonResponse({"success": False, "detail": "Invalid JSON payload"}, status=400)

    updates = {}
    if "pin_length" in data and data.get("pin_length") not in ("", None):
        try:
            updates["pin_length"] = int(data.get("pin_length"))
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "detail": "pin_length must be a number"}, status=400)

    if "anti_passback_window_hours" in data and data.get("anti_passback_window_hours") not in ("", None):
        try:
            updates["anti_passback_window_hours"] = int(data.get("anti_passback_window_hours"))
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "detail": "anti_passback_window_hours must be a number"}, status=400)

    for field in (
        "allow_sip_calls",
        "anti_passback_enabled",
        "anti_passback_enforce_no_reentry_without_exit",
        "anti_passback_allow_manual_override",
        "anti_passback_override_comment_required",
        "send_visitor_sms",
        "send_visitor_sms_otp",
        "send_visitor_sms_exitcode",
    ):
        if field in data:
            parsed = _parse_bool(data.get(field))
            if parsed is None:
                return JsonResponse({"success": False, "detail": f"{field} must be true or false"}, status=400)
            updates[field] = parsed

    if "anti_passback_warning_message" in data:
        updates["anti_passback_warning_message"] = str(data.get("anti_passback_warning_message") or "").strip()

    try:
        obj = update_runtime_settings(modified_by=request.user, **updates)
    except Exception as exc:
        return JsonResponse({"success": False, "detail": str(exc)}, status=400)

    return JsonResponse({"success": True, "settings": runtime_settings_payload(obj)})
