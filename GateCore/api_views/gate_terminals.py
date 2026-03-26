from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from GateCore.models import AccessPoint, AuditTrail, GateTerminal, Site
from GateCore.api_views.device_sync import build_sync_payload

DEVICE_PROFILE_CHOICES = {
    "rlapk_et7xx": {"model_name": "RLAPK ET7xx", "docking_mode": "local_cloud_platform"},
    "rlapk_et697xx": {"model_name": "RLAPK ET697xx", "docking_mode": "local_cloud_platform"},
    "rlapk_et739xx": {"model_name": "RLAPK ET739xx", "docking_mode": "local_cloud_platform"},
    "generic_ws_face": {"model_name": "Generic WebSocket Face Device", "docking_mode": "local_cloud_platform"},
}
DEVICE_LIVENESS_DETECTION_CHOICES = {"on", "off"}
DEVICE_FACE_GROUP_CONFIG_KEYS = ("default_face_group", "resident_face_group", "visitor_face_group")
DEVICE_VISITOR_QR_CONFIG_KEYS = (
    "visitor_call_status",
    "wxapp_visit_enable",
    "estate_id",
    "platform_id",
    "estate_name",
)


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_terminal_config(terminal: GateTerminal) -> dict:
    return terminal.config if isinstance(terminal.config, dict) else {}


def _extract_snapshot_config(config: dict) -> dict:
    snapshot = config.get("device_settings_snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _resolve_terminal_setting(config: dict, key: str, default=""):
    if key in config and config.get(key) not in (None, ""):
        return config.get(key)
    snapshot = _extract_snapshot_config(config)
    if key in snapshot and snapshot.get(key) not in (None, ""):
        return snapshot.get(key)
    return default


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _resolve_site(data):
    site_id = str(data.get("site_id") or "").strip()
    site_code = str(data.get("site_code") or "").strip()
    site_name = str(data.get("site_name") or "").strip()
    if site_id:
        try:
            return Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return None
    if site_code:
        try:
            return Site.objects.get(code=site_code)
        except Site.DoesNotExist:
            return None
    if site_name:
        try:
            return Site.objects.get(name__iexact=site_name)
        except Site.DoesNotExist:
            return None
    return None


def _resolve_access_point(data):
    access_point_id = str(data.get("access_point_id") or "").strip()
    if not access_point_id:
        return None
    try:
        return AccessPoint.objects.get(id=access_point_id)
    except AccessPoint.DoesNotExist:
        return None


def _resolve_device_profile(data):
    value = str(data.get("device_profile") or "").strip()
    if value in DEVICE_PROFILE_CHOICES:
        return value
    return ""


def _apply_device_profile(terminal: GateTerminal, data) -> list[str]:
    profile = _resolve_device_profile(data)
    if not profile:
        return []

    config = terminal.config if isinstance(terminal.config, dict) else {}
    next_config = dict(config)
    next_config["device_profile"] = profile
    next_config["protocol_profile"] = profile

    updates: list[str] = []
    if terminal.config != next_config:
        terminal.config = next_config
        updates.append("config")

    defaults = DEVICE_PROFILE_CHOICES.get(profile, {})
    model_name = defaults.get("model_name")
    docking_mode = defaults.get("docking_mode")
    if model_name and not str(data.get("model_name") or "").strip() and terminal.model_name != model_name:
        terminal.model_name = model_name
        updates.append("model_name")
    if docking_mode and not str(data.get("docking_mode") or "").strip() and terminal.docking_mode != docking_mode:
        terminal.docking_mode = docking_mode
        updates.append("docking_mode")
    return updates


def _apply_terminal_recognition_settings(terminal: GateTerminal, data) -> list[str]:
    config = _extract_terminal_config(terminal)
    next_config = dict(config)
    updated = False

    if "liveness_detection" in data:
        value = str(data.get("liveness_detection") or "").strip().lower()
        if value in DEVICE_LIVENESS_DETECTION_CHOICES:
            if next_config.get("liveness_detection") != value:
                next_config["liveness_detection"] = value
                updated = True
        elif value == "" and "liveness_detection" in next_config:
            next_config.pop("liveness_detection", None)
            updated = True

    for key in ("liveness_level", "recognition_level"):
        if key in data:
            raw_value = str(data.get(key) or "").strip()
            if raw_value == "":
                if key in next_config:
                    next_config.pop(key, None)
                    updated = True
                continue
            value = _coerce_int(raw_value)
            if value is not None and next_config.get(key) != value:
                next_config[key] = value
                updated = True

    if updated and next_config != config:
        terminal.config = next_config
        return ["config"]
    return []


def _apply_terminal_face_group_settings(terminal: GateTerminal, data) -> list[str]:
    config = _extract_terminal_config(terminal)
    next_config = dict(config)
    updated = False

    for key in DEVICE_FACE_GROUP_CONFIG_KEYS:
        if key not in data:
            continue
        raw_value = str(data.get(key) or "").strip()
        if raw_value:
            if next_config.get(key) != raw_value:
                next_config[key] = raw_value
                updated = True
        elif key in next_config:
            next_config.pop(key, None)
            updated = True

    if updated and next_config != config:
        terminal.config = next_config
        return ["config"]
    return []


def _apply_terminal_visitor_qr_settings(terminal: GateTerminal, data) -> list[str]:
    config = _extract_terminal_config(terminal)
    next_config = dict(config)
    updated = False

    for key in DEVICE_VISITOR_QR_CONFIG_KEYS:
        if key not in data:
            continue
        value = data.get(key)
        if key == "wxapp_visit_enable":
            if value in ("", None):
                if key in next_config:
                    next_config.pop(key, None)
                    updated = True
                continue
            text = str(value).strip().lower()
            normalized = 1 if text in {"1", "true", "yes", "on"} else 0
            if next_config.get(key) != normalized:
                next_config[key] = normalized
                updated = True
            continue

        raw_value = str(value or "").strip()
        if raw_value:
            if next_config.get(key) != raw_value:
                next_config[key] = raw_value
                updated = True
        elif key in next_config:
            next_config.pop(key, None)
            updated = True

    if updated and next_config != config:
        terminal.config = next_config
        return ["config"]
    return []


def _serialize_terminal(terminal: GateTerminal) -> dict:
    config = _extract_terminal_config(terminal)
    return {
        "id": str(terminal.id),
        "serial_number": terminal.serial_number,
        "display_name": terminal.display_name,
        "manufacturer": terminal.manufacturer or "",
        "model_name": terminal.model_name or "",
        "site_id": str(terminal.site.id) if terminal.site else "",
        "site_name": terminal.site.name if terminal.site else "",
        "access_point_id": str(terminal.access_point.id) if terminal.access_point else "",
        "direction": terminal.direction,
        "docking_mode": terminal.docking_mode,
        "server_url": terminal.server_url or "",
        "server_port": terminal.server_port if terminal.server_port is not None else "",
        "approval_status": terminal.approval_status,
        "is_approved": terminal.is_approved,
        "approved_at": terminal.approved_at.isoformat() if terminal.approved_at else "",
        "last_seen_at": terminal.last_seen_at.isoformat() if terminal.last_seen_at else "",
        "last_heartbeat_at": terminal.last_heartbeat_at.isoformat() if terminal.last_heartbeat_at else "",
        "firmware_version": terminal.firmware_version or "",
        "app_version": terminal.app_version or "",
        "ip_address": terminal.ip_address or "",
        "mac_address": terminal.mac_address or "",
        "sync_cursor": terminal.sync_cursor or {},
        "config": config,
        "device_profile": str(config.get("device_profile") or ""),
        "liveness_detection": _resolve_terminal_setting(config, "liveness_detection", ""),
        "liveness_level": _resolve_terminal_setting(config, "liveness_level", ""),
        "recognition_level": _resolve_terminal_setting(config, "recognition_level", ""),
        "default_face_group": _resolve_terminal_setting(config, "default_face_group", ""),
        "resident_face_group": _resolve_terminal_setting(config, "resident_face_group", ""),
        "visitor_face_group": _resolve_terminal_setting(config, "visitor_face_group", ""),
        "visitor_call_status": _resolve_terminal_setting(config, "visitor_call_status", ""),
        "wxapp_visit_enable": _resolve_terminal_setting(config, "wxapp_visit_enable", ""),
        "estate_id": _resolve_terminal_setting(config, "estate_id", ""),
        "platform_id": _resolve_terminal_setting(config, "platform_id", ""),
        "estate_name": _resolve_terminal_setting(config, "estate_name", ""),
        "notes": terminal.notes or "",
    }


class GateTerminalListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        forbidden = _require_staff(request)
        if forbidden:
            return forbidden
        rows = [_serialize_terminal(terminal) for terminal in GateTerminal.objects.select_related("site", "access_point").all()]
        return Response({"rows": rows, "gate_terminals": rows})

    def post(self, request):
        forbidden = _require_staff(request)
        if forbidden:
            return forbidden

        serial_number = str(request.data.get("serial_number") or "").strip()
        display_name = str(request.data.get("display_name") or "").strip()
        if not serial_number or not display_name:
            return Response(
                {"success": False, "error": "serial_number and display_name are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        site = _resolve_site(request.data)
        if not site:
            return Response(
                {"success": False, "error": "site_id or site_name is required. Select a site before creating the terminal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        terminal, created = GateTerminal.objects.get_or_create(
            serial_number=serial_number,
            defaults={
                "display_name": display_name,
                "manufacturer": str(request.data.get("manufacturer") or "").strip(),
                "model_name": str(request.data.get("model_name") or "").strip(),
                "direction": str(request.data.get("direction") or "entry").strip() or "entry",
                "docking_mode": str(request.data.get("docking_mode") or "local_cloud_platform").strip() or "local_cloud_platform",
                "server_url": str(request.data.get("server_url") or "").strip(),
                "server_port": request.data.get("server_port") or None,
                "approval_status": str(request.data.get("approval_status") or "pending").strip() or "pending",
                "site": site,
                "access_point": _resolve_access_point(request.data),
                "ip_address": str(request.data.get("ip_address") or "").strip(),
            },
        )

        if not created:
            terminal.display_name = display_name or terminal.display_name
            terminal.manufacturer = str(request.data.get("manufacturer") or terminal.manufacturer or "").strip()
            terminal.model_name = str(request.data.get("model_name") or terminal.model_name or "").strip()
            terminal.direction = str(request.data.get("direction") or terminal.direction).strip() or terminal.direction
            terminal.docking_mode = str(request.data.get("docking_mode") or terminal.docking_mode).strip() or terminal.docking_mode
            terminal.server_url = str(request.data.get("server_url") or terminal.server_url or "").strip()
            terminal.server_port = request.data.get("server_port") or terminal.server_port
            if "ip_address" in request.data:
                terminal.ip_address = str(request.data.get("ip_address") or "").strip()
            terminal.site = site
            if "access_point_id" in request.data:
                terminal.access_point = _resolve_access_point(request.data)
            profile_updates = _apply_device_profile(terminal, request.data)
            recognition_updates = _apply_terminal_recognition_settings(terminal, request.data)
            face_group_updates = _apply_terminal_face_group_settings(terminal, request.data)
            visitor_qr_updates = _apply_terminal_visitor_qr_settings(terminal, request.data)
            terminal.save(
                update_fields=[
                    "display_name",
                    "manufacturer",
                    "model_name",
                    "direction",
                    "docking_mode",
                    "server_url",
                    "server_port",
                    "ip_address",
                    "site",
                    "access_point",
                    *profile_updates,
                    *recognition_updates,
                    *face_group_updates,
                    *visitor_qr_updates,
                    "modified_at",
                ]
            )
        else:
            profile_updates = _apply_device_profile(terminal, request.data)
            recognition_updates = _apply_terminal_recognition_settings(terminal, request.data)
            face_group_updates = _apply_terminal_face_group_settings(terminal, request.data)
            visitor_qr_updates = _apply_terminal_visitor_qr_settings(terminal, request.data)
            if profile_updates or recognition_updates or face_group_updates or visitor_qr_updates:
                terminal.save(update_fields=[*profile_updates, *recognition_updates, *face_group_updates, *visitor_qr_updates, "modified_at"])

        AuditTrail.objects.create(
            action="edit" if not created else "create",
            performed_by=request.user if request.user.is_authenticated else None,
            details=f"Gate terminal {'created' if created else 'updated'}: {terminal.serial_number}",
        )
        return Response({"success": True, "terminal": _serialize_terminal(terminal)}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class GateTerminalDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, terminal_id):
        forbidden = _require_staff(request)
        if forbidden:
            return forbidden
        terminal = get_object_or_404(GateTerminal.objects.select_related("site", "access_point"), id=terminal_id)
        return Response({"terminal": _serialize_terminal(terminal)})

    def patch(self, request, terminal_id):
        forbidden = _require_staff(request)
        if forbidden:
            return forbidden
        terminal = get_object_or_404(GateTerminal, id=terminal_id)

        for field in ("display_name", "manufacturer", "model_name", "direction", "docking_mode", "server_url", "notes", "firmware_version", "app_version", "ip_address", "mac_address"):
            if field in request.data:
                setattr(terminal, field, request.data.get(field))
        if "server_port" in request.data:
            terminal.server_port = request.data.get("server_port") or None
        if "approval_status" in request.data:
            terminal.approval_status = request.data.get("approval_status") or terminal.approval_status
            if terminal.approval_status == "approved" and terminal.approved_at is None:
                terminal.approved_at = timezone.now()
        site = _resolve_site(request.data)
        if site:
            terminal.site = site
        if "access_point_id" in request.data:
            terminal.access_point = _resolve_access_point(request.data)
        _apply_device_profile(terminal, request.data)
        _apply_terminal_recognition_settings(terminal, request.data)
        _apply_terminal_face_group_settings(terminal, request.data)
        _apply_terminal_visitor_qr_settings(terminal, request.data)
        terminal.save()
        AuditTrail.objects.create(
            action="edit",
            performed_by=request.user if request.user.is_authenticated else None,
            details=f"Gate terminal updated: {terminal.serial_number}",
        )
        return Response({"success": True, "terminal": _serialize_terminal(terminal)})


@api_view(["POST"])
@permission_classes([AllowAny])
def gate_terminal_bootstrap(request):
    serial_number = str(request.data.get("serial_number") or "").strip()
    if not serial_number:
        return Response({"success": False, "error": "serial_number is required."}, status=status.HTTP_400_BAD_REQUEST)
    site = _resolve_site(request.data)
    if not site:
        return Response(
            {"success": False, "error": "site_id or site_name is required. Select a site before bootstrapping the terminal."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    defaults = {
        "display_name": str(request.data.get("display_name") or serial_number).strip() or serial_number,
        "manufacturer": str(request.data.get("manufacturer") or "").strip(),
        "model_name": str(request.data.get("model_name") or "").strip(),
        "direction": str(request.data.get("direction") or "entry").strip() or "entry",
        "docking_mode": str(request.data.get("docking_mode") or "local_cloud_platform").strip() or "local_cloud_platform",
        "server_url": str(request.data.get("server_url") or "").strip(),
        "server_port": request.data.get("server_port") or None,
        "site": site,
    }
    terminal, created = GateTerminal.objects.get_or_create(serial_number=serial_number, defaults=defaults)

    if not created:
        terminal.display_name = defaults["display_name"] or terminal.display_name
        terminal.manufacturer = defaults["manufacturer"] or terminal.manufacturer
        terminal.model_name = defaults["model_name"] or terminal.model_name
        terminal.direction = defaults["direction"] or terminal.direction
        terminal.docking_mode = defaults["docking_mode"] or terminal.docking_mode
        terminal.server_url = defaults["server_url"] or terminal.server_url
        terminal.server_port = defaults["server_port"] or terminal.server_port
        if defaults["site"]:
            terminal.site = defaults["site"]
        terminal.last_seen_at = timezone.now()
        terminal.last_heartbeat_at = timezone.now()
        terminal.save(
            update_fields=[
                "display_name",
                "manufacturer",
                "model_name",
                "direction",
                "docking_mode",
                "server_url",
                "server_port",
                "site",
                "last_seen_at",
                "last_heartbeat_at",
                "modified_at",
            ]
        )
    else:
        terminal.last_seen_at = timezone.now()
        terminal.last_heartbeat_at = timezone.now()
        terminal.save(update_fields=["last_seen_at", "last_heartbeat_at", "modified_at"])

    approved = terminal.approval_status == "approved"
    payload = _serialize_terminal(terminal)
    payload["sync_allowed"] = approved
    payload["server_state"] = terminal.approval_status
    payload["bootstrap_state"] = "created" if created else "updated"
    return Response({"success": True, "terminal": payload})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gate_terminal_sync_preview(request, terminal_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    terminal = get_object_or_404(GateTerminal.objects.select_related("site", "access_point"), id=terminal_id)
    cursor_value = request.query_params.get("cursor")
    cursor = None
    if cursor_value:
        cursor = parse_datetime(cursor_value)

    limit_value = request.query_params.get("limit")
    full_value = str(request.query_params.get("full") or "").strip().lower()
    max_items = 20
    if full_value in {"1", "true", "yes", "on"}:
        max_items = None
    elif limit_value not in {None, ""}:
        try:
            max_items = max(1, min(int(limit_value), 100))
        except (TypeError, ValueError):
            max_items = 20

    payload, next_cursor = build_sync_payload(terminal.serial_number, cursor, max_items=max_items)
    sync_job = terminal.serial_number
    response = {
        "success": True,
        "terminal": _serialize_terminal(terminal),
        "preview": payload,
        "preview_meta": {
            "next_cursor": next_cursor.isoformat() if next_cursor else "",
            "sync_job": sync_job,
            "preview_limit": max_items if max_items is not None else "",
        },
    }
    return Response(response)
