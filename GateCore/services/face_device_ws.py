import logging
import json
import base64
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import quote, urlparse, urlunparse
from typing import Any

from django.conf import settings
from django.db import OperationalError
from django.utils import timezone

from GateCore.api_views.device_sync import build_sync_payload
from GateCore.models import DeviceSyncJob, GateTerminal
from face_devices.models import FaceDeviceAccessLog
from face_devices.services import (
    dequeue_pending_actions,
    ingest_face_device_access_log,
    refresh_face_device_user_state,
    record_face_device_event,
    resolve_action_result,
)

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

DEFAULT_DEVICE_SETTINGS = {
    "facial_recognition_enabled": True,
    "sync_enabled": True,
    "sync_mode": "websocket",
}
ACCESS_LOG_PROBE_COOLDOWN = timedelta(hours=1)
ACCESS_LOG_PROBE_NO_LOGS_COOLDOWN = timedelta(minutes=2)
VISITOR_QR_SETTING_KEYS = (
    "visitor_call_status",
    "wxapp_visit_enable",
    "qrcode_url",
    "test_qrcode_url",
    "web_qrcode_url",
    "local_qrcode_url",
    "estate_id",
    "platform_id",
    "estate_name",
)


@dataclass
class WsCommandResult:
    response: dict[str, Any]
    close: bool = False
    follow_ups: list[dict[str, Any]] | None = None


def _now_iso() -> str:
    return timezone.now().isoformat()


def _format_device_datetime(value: Any) -> str:
    if not value:
        return ""
    dt_value = value
    # If value is an ISO-format string, parse it into a datetime first.
    if isinstance(dt_value, str):
        try:
            from django.utils.dateparse import parse_datetime as _parse_dt
            parsed = _parse_dt(dt_value)
            if parsed is not None:
                dt_value = parsed
        except Exception:
            pass
    try:
        if hasattr(dt_value, "tzinfo") and dt_value.tzinfo is not None:
            dt_value = timezone.localtime(dt_value)
    except Exception:
        pass
    if hasattr(dt_value, "strftime"):
        return dt_value.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt_value)


def _safe_json_loads(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _summarize_mapping(payload: dict[str, Any], limit: int = 1200) -> str:
    if not payload:
        return "{}"
    try:
        text = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    except Exception:
        text = str(payload)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated>"


def _response_command(command: str) -> str:
    mapping = {
        "declare": "declareRet",
        "getDeviceSettings": "getDeviceSettingsRet",
        "getUserInfo": "getUserInfoRet",
        "getGroups": "getGroupsRet",
        "getRecord": "getRecordRet",
        "getAccessRecord": "getAccessRecordRet",
        "getPassRecord": "getPassRecordRet",
        "addUser": "addUserRet",
        "editUser": "editUserRet",
        "createGroup": "createGroupRet",
        "deleteGroup": "deleteGroupRet",
        "delUser": "delUserRet",
        "delMultiUser": "delMultiUserRet",
        "delAllUser": "delAllUserRet",
        "uploadFaceInfo": "uploadFaceInfoRet",
        "ping": "ping",
        "heartbeat": "heartbeat",
        "": "ping",
    }
    return mapping.get(command, command or "unknown")


def _build_server_command(
    command: str,
    device_identifier: str,
    *,
    settings: list[str] | None = None,
    remote_ip: str | None = None,
    device_type: str = "device",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "cmd": command,
        "sn": device_identifier,
        "timestamp": int(timezone.now().timestamp()),
        "type": device_type,
    }
    if remote_ip:
        payload["ip"] = remote_ip
    if settings is not None:
        payload["settings"] = settings
    if extra:
        payload.update(extra)
    return payload


def _preserve_probe_flags(existing_payload: Any, next_payload: dict[str, Any]) -> dict[str, Any]:
    preserved = next_payload
    if not isinstance(existing_payload, dict):
        return preserved
    for key in ("user_ids_probe_attempted", "access_logs_probe_attempted", "access_logs_probe_commands"):
        if key in existing_payload and key not in preserved:
            preserved[key] = existing_payload.get(key)
    return preserved


def _terminal_config_value(terminal: GateTerminal | None, key: str, default: Any = "") -> Any:
    if terminal is None or not isinstance(terminal.config, dict):
        return default
    config_value = terminal.config.get(key)
    if config_value not in (None, ""):
        return config_value
    snapshot = terminal.config.get("device_settings_snapshot")
    if isinstance(snapshot, dict):
        snapshot_value = snapshot.get(key)
        if snapshot_value not in (None, ""):
            return snapshot_value
    return default


def _derive_websocket_urls(server_url: str, server_port: Any) -> tuple[str, str]:
    raw_url = str(server_url or "").strip()
    raw_port = "" if server_port in {None, ""} else str(server_port).strip()
    if not raw_url:
        return "", ""

    normalized = raw_url
    if normalized.startswith("http://"):
        normalized = "ws://" + normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = "wss://" + normalized[len("https://") :]

    root_url = normalized.rstrip("/")
    if raw_port and ":" not in root_url.split("://", 1)[-1].split("/", 1)[0]:
        root_url = f"{root_url}:{raw_port}"
    ws_root = root_url + "/"
    ws_path = root_url + "/ws"
    return ws_root, ws_path


def _preferred_websocket_urls(server_url: str, server_port: Any) -> tuple[str, str]:
    explicit_ws_url = str(getattr(settings, "FACE_SYNC_WS_URL", "") or "").strip()
    explicit_ws_path = str(getattr(settings, "FACE_SYNC_WS_PATH_URL", "") or "").strip()
    if explicit_ws_url or explicit_ws_path:
        ws_root = explicit_ws_url or explicit_ws_path.rstrip("/ws").rstrip("/") + "/"
        ws_path = explicit_ws_path or ws_root.rstrip("/") + "/ws"
        return ws_root, ws_path

    raw_url = str(server_url or "").strip()
    ws_port = str(getattr(settings, "FACE_SYNC_WS_PORT", 12391))
    if raw_url:
        parsed = urlparse(raw_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        hostname = parsed.hostname or ""
        if hostname:
            netloc = f"{hostname}:{ws_port}"
            root = urlunparse((scheme, netloc, "/", "", "", ""))
            path = urlunparse((scheme, netloc, "/ws", "", "", ""))
            return root, path
    return _derive_websocket_urls(server_url, server_port)


def _normalize_http_base_url(raw_url: str) -> str:
    text = str(raw_url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")


def _resolve_terminal_estate_id(terminal: GateTerminal | None) -> str:
    estate_id = str(_terminal_config_value(terminal, "estate_id", "") or "").strip()
    if estate_id:
        return estate_id
    if terminal and terminal.site_id:
        return "1"
    return ""


def _build_terminal_application_entry_url(
    terminal: GateTerminal | None,
    *,
    device_identifier: str,
    server_url: str,
) -> str:
    if terminal is None:
        return ""
    base_url = _normalize_http_base_url(server_url)
    if not base_url:
        base_url = _normalize_http_base_url(getattr(settings, "VISITOR_FACE_ENROLLMENT_URL_BASE", ""))
    if not base_url:
        return ""
    estate_id = _resolve_terminal_estate_id(terminal)
    query = []
    if estate_id:
        query.append(f"estate_id={quote(estate_id, safe='')}")
    if device_identifier:
        query.append(f"sn={quote(device_identifier, safe='')}")
    suffix = f"?{'&'.join(query)}" if query else ""
    return f"{base_url}/visitor/application-entry/{suffix}"


def _extract_command(message: str | dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if isinstance(message, dict):
        record = message
    elif isinstance(message, str):
        parsed = _safe_json_loads(message)
        if parsed is not None:
            record = parsed
        else:
            return message.strip(), {}
    else:
        return "", {}

    command = ""
    for key in ("command", "cmd", "action", "type", "name", "op"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            command = value.strip()
            break
    if command in {"to_client", "to_device"}:
        nested = record.get("data")
        if isinstance(nested, dict):
            nested_command = nested.get("cmd")
            if isinstance(nested_command, str) and nested_command.strip():
                merged = dict(nested)
                for passthrough_key in ("from", "form", "to", "extra"):
                    if passthrough_key in record and passthrough_key not in merged:
                        merged[passthrough_key] = record.get(passthrough_key)
                command = nested_command.strip()
                record = merged
    if not command and isinstance(record.get("message"), str):
        command = str(record["message"]).strip()
    return command, record


def _resolve_device_identifier(payload: dict[str, Any], remote_ip: str | None = None) -> str:
    for key in ("device_identifier", "deviceId", "device_id", "sn", "serial_number", "serialNo", "serial"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("from", "form", "client_id", "to"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if remote_ip:
        return remote_ip
    return "face-device"


def _resolve_device_name(payload: dict[str, Any], remote_ip: str | None = None) -> str:
    for key in ("device_name", "deviceName", "name", "display_name", "terminal_name", "model_name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if remote_ip:
        return f"face-device@{remote_ip}"
    return "face-device"


def _ensure_sync_job(device_identifier: str, device_name: str = "") -> DeviceSyncJob:
    job, _ = DeviceSyncJob.objects.get_or_create(
        device_identifier=device_identifier,
        defaults={"device_name": device_name},
    )
    if device_name and job.device_name != device_name:
        job.device_name = device_name
        job.save(update_fields=["device_name", "modified_at"])
    return job


def _select_terminal(device_identifier: str, remote_ip: str | None = None) -> GateTerminal | None:
    terminal = GateTerminal.objects.select_related("site", "access_point").filter(serial_number=device_identifier).first()
    if terminal:
        return terminal
    terminal = GateTerminal.objects.select_related("site", "access_point").filter(display_name__iexact=device_identifier).first()
    if terminal:
        return terminal
    if remote_ip:
        return GateTerminal.objects.select_related("site", "access_point").filter(ip_address=remote_ip).first()
    return None


def _update_terminal_presence(
    terminal: GateTerminal | None,
    payload: dict[str, Any],
    *,
    remote_ip: str | None = None,
    command: str = "",
) -> GateTerminal | None:
    if terminal is None:
        return None

    update_fields: list[str] = []
    now = timezone.now()
    terminal.last_seen_at = now
    update_fields.append("last_seen_at")
    if command in {"", "ping", "heartbeat", "declare"}:
        terminal.last_heartbeat_at = now
        update_fields.append("last_heartbeat_at")

    if remote_ip and terminal.ip_address != remote_ip:
        terminal.ip_address = remote_ip
        update_fields.append("ip_address")

    version_name = payload.get("version_name")
    if isinstance(version_name, str) and version_name.strip() and terminal.app_version != version_name.strip():
        terminal.app_version = version_name.strip()
        update_fields.append("app_version")

    version_code = payload.get("version_code")
    if isinstance(version_code, str) and version_code.strip() and terminal.firmware_version != version_code.strip():
        terminal.firmware_version = version_code.strip()
        update_fields.append("firmware_version")

    device_type = payload.get("type")
    if isinstance(device_type, str) and device_type.strip() and terminal.model_name != device_type.strip():
        terminal.model_name = device_type.strip()
        update_fields.append("model_name")

    if update_fields:
        terminal.save(update_fields=[*sorted(set(update_fields)), "modified_at"])
    return terminal


def build_device_settings(device_identifier: str, device_name: str = "", *, remote_ip: str | None = None) -> dict[str, Any]:
    terminal = _select_terminal(device_identifier, remote_ip=remote_ip)
    approved = bool(terminal and terminal.is_approved)
    resolved_device_name = terminal.display_name if terminal and terminal.display_name else (device_name or device_identifier)
    server_url = terminal.server_url if terminal else ""
    server_port = terminal.server_port if terminal and terminal.server_port is not None else ""

    # Some approved terminals are missing explicit API endpoint fields.
    # Reuse the most recently configured terminal endpoint as a safe fallback so devices can still upload logs.
    if approved and not str(server_url or "").strip():
        fallback_terminal = (
            GateTerminal.objects.filter(approval_status="approved")
            .exclude(server_url__isnull=True)
            .exclude(server_url__exact="")
            .order_by("-modified_at")
            .first()
        )
        if fallback_terminal:
            server_url = fallback_terminal.server_url or server_url
            if server_port in (None, ""):
                server_port = fallback_terminal.server_port if fallback_terminal.server_port is not None else server_port

    ws_server_url, ws_server_url_path = _preferred_websocket_urls(server_url, server_port)
    token_key = "token"
    token_value = str(getattr(settings, "GATE_DEVICE_SYNC_TOKEN", "") or "")
    if terminal and isinstance(terminal.config, dict):
        maybe_key = terminal.config.get("token_key")
        maybe_value = terminal.config.get("token_value")
        if isinstance(maybe_key, str) and maybe_key.strip():
            token_key = maybe_key.strip()
        if isinstance(maybe_value, str):
            token_value = maybe_value.strip()
    advertised_server_url = ws_server_url or server_url
    advertised_server_port = getattr(settings, "FACE_SYNC_WS_PORT", 12391) if ws_server_url else server_port
    application_entry_url = _build_terminal_application_entry_url(
        terminal,
        device_identifier=device_identifier,
        server_url=server_url,
    )
    settings_payload = dict(DEFAULT_DEVICE_SETTINGS)
    settings_payload.update(
        {
            "device_identifier": device_identifier,
            "device_name": resolved_device_name,
            "server_url": advertised_server_url,
            "server_port": advertised_server_port,
            "api_server_url": server_url,
            "api_server_port": server_port,
            "ws_server_url": ws_server_url,
            "websocket_url": ws_server_url,
            "ws_server_url_path": ws_server_url_path,
            "websocket_url_path": ws_server_url_path,
            "token_key": token_key,
            "token_value": token_value,
            "approval_status": terminal.approval_status if terminal else "",
            "approved": approved,
            "sync_allowed": approved,
            "site_name": terminal.site.name if terminal and terminal.site else "",
            "direction": terminal.direction if terminal else "",
            "docking_mode": terminal.docking_mode if terminal else "",
            "liveness_detection": _terminal_config_value(terminal, "liveness_detection", "on"),
            "liveness_level": _terminal_config_value(terminal, "liveness_level", ""),
            "recognition_level": _terminal_config_value(terminal, "recognition_level", ""),
            "default_face_group": _terminal_config_value(terminal, "default_face_group", ""),
            "resident_face_group": _terminal_config_value(terminal, "resident_face_group", ""),
            "visitor_face_group": _terminal_config_value(terminal, "visitor_face_group", ""),
            "estate_id": _resolve_terminal_estate_id(terminal),
            "platform_id": _terminal_config_value(terminal, "platform_id", _resolve_terminal_estate_id(terminal)),
            "estate_name": _terminal_config_value(terminal, "estate_name", terminal.site.name if terminal and terminal.site else ""),
            "last_seen_at": terminal.last_seen_at.isoformat() if terminal and terminal.last_seen_at else "",
            "last_heartbeat_at": terminal.last_heartbeat_at.isoformat() if terminal and terminal.last_heartbeat_at else "",
        }
    )
    for key in VISITOR_QR_SETTING_KEYS:
        if key in {"qrcode_url", "test_qrcode_url", "web_qrcode_url", "local_qrcode_url"}:
            if application_entry_url:
                settings_payload[key] = application_entry_url
            continue
        value = _terminal_config_value(terminal, key, None)
        if value not in (None, ""):
            settings_payload[key] = value
    return settings_payload


def build_user_sync(device_identifier: str, cursor: str | None = None) -> dict[str, Any]:
    cursor_dt = None
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except Exception:
            cursor_dt = None
    payload, next_cursor = build_sync_payload(device_identifier, cursor_dt)
    approved_people = payload.get("approved_people", [])
    revoked_people = payload.get("revoked_people", [])
    units = payload.get("units", [])
    return {
        "device_identifier": device_identifier,
        "cursor": payload.get("cursor", ""),
        "next_cursor": payload.get("next_cursor", next_cursor.isoformat() if next_cursor else ""),
        "server_time": payload.get("server_time", _now_iso()),
        "approved_people": approved_people,
        "revoked_people": revoked_people,
        "units": units,
        "people": approved_people,
        "users": approved_people,
        "rows": approved_people,
        "list": approved_people,
        "dataList": approved_people,
        "all_people": approved_people,
        "all_users": approved_people,
        "removed_people": revoked_people,
        "removed_users": revoked_people,
        "counts": payload.get("counts", {}),
        "truncated": payload.get("truncated", False),
        "max_items": payload.get("max_items", ""),
    }


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _should_send_access_log_probe(terminal: GateTerminal | None, device_identifier: str) -> bool:
    has_logs = FaceDeviceAccessLog.objects.filter(device_identifier=device_identifier).exists()

    cooldown = ACCESS_LOG_PROBE_COOLDOWN if has_logs else ACCESS_LOG_PROBE_NO_LOGS_COOLDOWN
    if terminal is None or not isinstance(terminal.config, dict):
        return True
    raw = terminal.config.get("last_access_log_probe_at")
    if not isinstance(raw, str) or not raw.strip():
        return True
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return True
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return timezone.now() - parsed >= cooldown


def _mark_access_log_probe_sent(terminal: GateTerminal | None) -> None:
    if terminal is None:
        return
    config = terminal.config if isinstance(terminal.config, dict) else {}
    next_config = dict(config)
    next_config["last_access_log_probe_at"] = timezone.now().isoformat()
    if next_config != config:
        terminal.config = next_config
        terminal.save(update_fields=["config", "modified_at"])


def _prepare_face_template(image_value: Any) -> str:
    raw_value = str(image_value or "").strip()
    if not raw_value:
        return ""
    if Image is None:
        if raw_value.startswith("data:image/") and ";base64," in raw_value:
            return raw_value.split(",", 1)[1]
        return raw_value

    encoded = raw_value
    if raw_value.startswith("data:image/") and ";base64," in raw_value:
        _, encoded = raw_value.split(",", 1)

    try:
        image_bytes = base64.b64decode(encoded)
        with Image.open(io.BytesIO(image_bytes)) as source_image:
            image = source_image.convert("RGB")
            width, height = image.size
            crop_left = max(0, int(width * 0.18))
            crop_top = max(0, int(height * 0.12))
            crop_right = min(width, int(width * 0.82))
            crop_bottom = min(height, int(height * 0.92))
            if crop_right - crop_left >= 200 and crop_bottom - crop_top >= 200:
                image = image.crop((crop_left, crop_top, crop_right, crop_bottom))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=95)
        return base64.b64encode(output.getvalue()).decode("ascii")
    except Exception:
        return encoded


def _select_add_user_probe(sync_payload: dict[str, Any]) -> dict[str, Any] | None:
    approved_people = sync_payload.get("approved_people")
    if not isinstance(approved_people, list):
        return None

    for person in approved_people:
        if not isinstance(person, dict):
            continue
        payload = _build_add_user_payload(person)
        if payload:
            return payload
    return None


def _build_add_user_payload(person: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(person, dict):
        return None
    user_id = str(person.get("face_subject_id") or person.get("id") or "").strip()
    full_name = str(person.get("full_name") or "").strip()
    id_number = str(person.get("id_number") or person.get("phone") or user_id).strip()
    face_template = _prepare_face_template(person.get("photo_url"))
    if not user_id or not full_name or not face_template:
        return None
    payload = {
        "user_id": user_id,
        "id_name": full_name,
        "name": full_name,
        "id_number": id_number,
        "id_card": id_number,
        "phone": str(person.get("phone") or "").strip(),
        "face_template": face_template,
        "tts_name": str(person.get("face_tts_name") or full_name).strip(),
    }
    face_group_name = str(person.get("face_group_name") or "").strip()
    if face_group_name:
        payload["face_group_name"] = face_group_name
    card_number = str(person.get("card_number") or "").strip()
    if card_number:
        payload["Ic"] = card_number

    user_type = person.get("face_user_type")
    if user_type not in (None, ""):
        payload["user_type"] = _coerce_int(user_type, default=0)

    is_visitor = bool(person.get("is_visitor"))

    effect_time = person.get("face_effective_from") if is_visitor else None
    if effect_time not in (None, ""):
        payload["effect_time"] = _format_device_datetime(effect_time)

    valid_until = person.get("face_valid_until") if is_visitor else None
    if valid_until not in (None, ""):
        rendered_valid_until = _format_device_datetime(valid_until)
        payload["end_time"] = rendered_valid_until
        payload["valid_until"] = rendered_valid_until

    access_password = str(person.get("face_access_password") or "").strip()
    if access_password:
        payload["password"] = access_password

    pass_rule_id = str(person.get("face_pass_rule_id") or "").strip()
    if pass_rule_id:
        payload["pass_rule_id"] = pass_rule_id

    max_pass_count = person.get("face_max_pass_count")
    if max_pass_count not in (None, ""):
        payload["max_pass_count"] = _coerce_int(max_pass_count, default=0)

    pass_count_cycle = person.get("face_pass_count_cycle")
    if pass_count_cycle not in (None, ""):
        payload["pass_count_cycle"] = _coerce_int(pass_count_cycle, default=0)
    return payload


def _sync_approved_people_by_id(sync_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    approved_people = sync_payload.get("approved_people")
    if not isinstance(approved_people, list):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for person in approved_people:
        payload = _build_add_user_payload(person)
        if payload:
            result[payload["user_id"]] = payload
    return result


def handle_message(message: str | dict[str, Any], *, remote_ip: str | None = None) -> WsCommandResult:
    command, payload = _extract_command(message)
    device_identifier = _resolve_device_identifier(payload, remote_ip=remote_ip)
    device_name = _resolve_device_name(payload, remote_ip=remote_ip)
    job = _ensure_sync_job(device_identifier, device_name=device_name)
    terminal = _update_terminal_presence(
        _select_terminal(device_identifier, remote_ip=remote_ip),
        payload,
        remote_ip=remote_ip,
        command=command,
    )

    request_keys = ",".join(sorted(payload.keys())) if payload else "<none>"
    print(
        f"face-device-sync request command={command or '<empty>'} device={device_identifier} remote={remote_ip or '<unknown>'} payload_keys={request_keys}",
        flush=True,
    )
    print(
        "face-device-sync request details "
        f"device={device_identifier} terminal_found={'yes' if terminal else 'no'} "
        f"approval={(terminal.approval_status if terminal else '<missing>')} "
        f"payload={_summarize_mapping(payload)}",
        flush=True,
    )
    record_face_device_event(
        terminal=terminal,
        device_identifier=device_identifier,
        direction="inbound",
        command=command or "unknown",
        payload=payload,
        status="received",
        remote_ip=remote_ip,
    )
    created_access_logs = ingest_face_device_access_log(
        terminal=terminal,
        device_identifier=device_identifier,
        command=command,
        payload=payload,
        remote_ip=remote_ip,
    )
    if created_access_logs:
        print(
            "face-device-sync access-log-ingest "
            f"device={device_identifier} command={command or '<empty>'} created={len(created_access_logs)}",
            flush=True,
        )
    if command.endswith("Ret") or payload.get("extra"):
        resolve_action_result(device_identifier=device_identifier, payload=payload, command=command)

    cursor = payload.get("cursor")
    if not isinstance(cursor, str):
        cursor = str(job.cursor_at.isoformat()) if job.cursor_at else ""

    base_response = {
        "cmd": _response_command(command),
        "sn": device_identifier,
        "ip": payload.get("ip") if isinstance(payload.get("ip"), str) else (remote_ip or ""),
        "type": payload.get("type") if isinstance(payload.get("type"), str) else "",
        "version_code": payload.get("version_code") if isinstance(payload.get("version_code"), str) else "",
        "version_name": payload.get("version_name") if isinstance(payload.get("version_name"), str) else "",
        "server_time": _now_iso(),
        "success": True,
        "code": 0,
        "msg": "success",
    }
    settings_payload = build_device_settings(device_identifier, device_name=device_name, remote_ip=remote_ip)
    approved = bool(settings_payload.get("approved"))
    action_follow_ups = dequeue_pending_actions(
        terminal=terminal,
        device_identifier=device_identifier,
        remote_ip=remote_ip,
        device_type=base_response["type"] or "device",
    )

    def _with_action_follow_ups(follow_ups: list[dict[str, Any]] | None = None) -> list[dict[str, Any]] | None:
        merged: list[dict[str, Any]] = []
        if follow_ups:
            merged.extend(follow_ups)
        if action_follow_ups:
            merged.extend(action_follow_ups)
        return merged or None

    if command in {"", "ping", "heartbeat"}:
        ping_payload = dict(base_response)
        ping_payload.update(
            {
                "data": {
                    "cmd": _response_command(command),
                    "sn": device_identifier,
                    "ip": base_response["ip"],
                    "type": base_response["type"],
                    "version_code": base_response["version_code"],
                    "version_name": base_response["version_name"],
                    "server_time": base_response["server_time"],
                    "success": True,
                    "code": 0,
                    "msg": "success",
                },
                "device_name": device_name,
                "approved": approved,
                "sync_allowed": settings_payload.get("sync_allowed", approved),
                "server_url": settings_payload.get("server_url", ""),
                "server_port": settings_payload.get("server_port", ""),
                "facial_recognition_enabled": settings_payload.get("facial_recognition_enabled", True),
                "sync_enabled": settings_payload.get("sync_enabled", True),
                "sync_mode": settings_payload.get("sync_mode", "websocket"),
            }
        )
        print(
            "face-device-sync response command="
            f"{command or 'ping'} device={device_identifier} "
            f"approved={ping_payload['approved']} sync_allowed={ping_payload['sync_allowed']} "
            f"server_url={ping_payload['server_url'] or '<empty>'} server_port={ping_payload['server_port'] or '<empty>'}",
            flush=True,
        )
        return WsCommandResult(response=ping_payload, follow_ups=_with_action_follow_ups())

    if command == "declare":
        response = dict(base_response)
        response.update(
            {
                "data": settings_payload,
                "settings": ["all"],
                "device_name": device_name,
                "approved": approved,
                "sync_allowed": settings_payload.get("sync_allowed", approved),
                "server_url": settings_payload.get("server_url", ""),
                "server_port": settings_payload.get("server_port", ""),
                "facial_recognition_enabled": settings_payload.get("facial_recognition_enabled", True),
                "sync_enabled": settings_payload.get("sync_enabled", True),
                "sync_mode": settings_payload.get("sync_mode", "websocket"),
            }
        )
        follow_ups = [
            _build_server_command(
                "getDeviceSettings",
                device_identifier,
                settings=["all"],
                remote_ip=remote_ip,
                device_type=base_response["type"] or "device",
            )
        ]
        print(
            "face-device-sync response command=declare "
            f"device={device_identifier} response_cmd={response['cmd']} keys={','.join(sorted(response.keys()))} "
            f"approved={response['approved']} sync_allowed={response['sync_allowed']} "
            f"server_url={response['server_url'] or '<empty>'} server_port={response['server_port'] or '<empty>'} "
            f"ws_server_url={settings_payload.get('ws_server_url') or '<empty>'} "
            f"ws_server_url_path={settings_payload.get('ws_server_url_path') or '<empty>'} "
            f"token_key={settings_payload.get('token_key') or '<empty>'} "
            f"follow_ups={','.join(item.get('cmd', '<unknown>') for item in follow_ups) or '<none>'} "
            f"data={_summarize_mapping(settings_payload)}",
            flush=True,
        )
        return WsCommandResult(response=response, follow_ups=_with_action_follow_ups(follow_ups))

    if command == "getDeviceSettingsRet":
        reported_settings = payload.get("settings")
        if not isinstance(reported_settings, dict):
            reported_settings = {}

        job.last_synced_at = timezone.now()
        job.last_status = "success"
        job.last_error = ""
        job.last_payload = {
            "command": command,
            "device_identifier": device_identifier,
            "settings": reported_settings,
            "payload": payload,
        }
        job.save(update_fields=["last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])

        if terminal and isinstance(terminal.config, dict):
            next_config = dict(terminal.config)
            next_config["device_settings_snapshot"] = reported_settings
            next_config["device_settings_received_at"] = _now_iso()
            client_id = payload.get("client_id") or payload.get("from") or payload.get("form")
            if isinstance(client_id, str) and client_id.strip():
                next_config["device_client_id"] = client_id.strip()
            terminal.config = next_config
            terminal.save(update_fields=["config", "modified_at"])

        follow_ups = [
            _build_server_command(
                "getUserInfo",
                device_identifier,
                remote_ip=remote_ip,
                device_type=base_response["type"] or "device",
                extra={"value": 0},
            )
        ]
        print(
            "face-device-sync response command=getDeviceSettingsRet "
            f"device={device_identifier} code={payload.get('code')} "
            f"settings_count={len(reported_settings)} "
            f"follow_ups={','.join(item.get('cmd', '<unknown>') for item in follow_ups)}",
            flush=True,
        )
        return WsCommandResult(response={}, follow_ups=_with_action_follow_ups(follow_ups))

    if command == "getDeviceSettings":
        response = dict(base_response)
        response.update(
            {
                "data": settings_payload,
                "settings": ["all"],
                "cursor": cursor,
                "device_name": device_name,
                "approved": approved,
                "sync_allowed": settings_payload.get("sync_allowed", approved),
                "server_url": settings_payload.get("server_url", ""),
                "server_port": settings_payload.get("server_port", ""),
                "facial_recognition_enabled": settings_payload.get("facial_recognition_enabled", True),
                "sync_enabled": settings_payload.get("sync_enabled", True),
                "sync_mode": settings_payload.get("sync_mode", "websocket"),
            }
        )
        print(
            "face-device-sync response command=getDeviceSettings "
            f"device={device_identifier} response_cmd={response['cmd']} keys={','.join(sorted(response.keys()))} "
            f"approved={response.get('approved', approved)} sync_allowed={settings_payload.get('sync_allowed', approved)} "
            f"data={_summarize_mapping(settings_payload)}",
            flush=True,
        )
        return WsCommandResult(response=response, follow_ups=_with_action_follow_ups())

    if command == "getUserInfoRet":
        total = _coerce_int(payload.get("total"), default=-1)
        sync_payload = build_user_sync(device_identifier, cursor=cursor)
        approved_people_by_id = _sync_approved_people_by_id(sync_payload)
        approved_user_ids = list(approved_people_by_id.keys())
        raw_reported_user_ids = payload.get("userIds")
        reported_user_ids_available = isinstance(raw_reported_user_ids, list)
        reported_user_ids = raw_reported_user_ids if reported_user_ids_available else []
        try:
            refresh_face_device_user_state(
                terminal=terminal,
                device_identifier=device_identifier,
                approved_user_ids=approved_user_ids,
                reported_user_ids=[str(item).strip() for item in reported_user_ids if str(item).strip()],
                payload=payload,
            )
        except OperationalError as exc:
            print(
                "face-device-sync warning refresh_face_device_user_state "
                f"device={device_identifier} error={str(exc)}",
                flush=True,
            )
        follow_ups: list[dict[str, Any]] = []
        probe_user = None
        queued_missing_users = 0
        last_payload = job.last_payload if isinstance(job.last_payload, dict) else {}
        already_probed_user_ids = bool(last_payload.get("user_ids_probe_attempted"))
        already_probed_access_logs = bool(last_payload.get("access_logs_probe_attempted"))
        if reported_user_ids_available:
            normalized_reported_ids = {str(item).strip() for item in reported_user_ids if str(item).strip()}
            missing_user_ids = [user_id for user_id in approved_user_ids if user_id not in normalized_reported_ids]
            if missing_user_ids:
                for missing_user_id in missing_user_ids:
                    probe_user = approved_people_by_id.get(missing_user_id)
                    if not probe_user:
                        continue
                    follow_ups.append(
                        _build_server_command(
                            "addUser",
                            device_identifier,
                            remote_ip=remote_ip,
                            device_type=base_response["type"] or "device",
                            extra=probe_user,
                        )
                    )
                    queued_missing_users += 1
                if missing_user_ids:
                    probe_user = approved_people_by_id.get(missing_user_ids[0])
        elif total >= 0 and total != len(approved_user_ids):
            if not already_probed_user_ids:
                follow_ups.append(
                    _build_server_command(
                        "getUserInfo",
                        device_identifier,
                        remote_ip=remote_ip,
                        device_type=base_response["type"] or "device",
                        extra={"value": 2},
                    )
                )
            elif approved_user_ids:
                # Device does not expose userIds; avoid infinite probes and still attempt sync.
                for user_id in approved_user_ids:
                    probe_user = approved_people_by_id.get(user_id)
                    if not probe_user:
                        continue
                    follow_ups.append(
                        _build_server_command(
                            "addUser",
                            device_identifier,
                            remote_ip=remote_ip,
                            device_type=base_response["type"] or "device",
                            extra=probe_user,
                        )
                    )
                    queued_missing_users += 1

        record_probe_commands = ["getRecord", "getAccessRecord", "getPassRecord"]
        if total > 0 and _should_send_access_log_probe(terminal, device_identifier):
            for probe_command in record_probe_commands:
                request_id = uuid.uuid4().hex
                # Structured probe (works for some firmware variants).
                follow_ups.append(
                    _build_server_command(
                        probe_command,
                        device_identifier,
                        remote_ip=remote_ip,
                        device_type=base_response["type"] or "device",
                        extra={
                            "value": 0,
                            "headers": {"req_id": request_id},
                            "body": {
                                "sn": device_identifier,
                                "timestamp": int(timezone.now().timestamp()),
                                "type": base_response["type"] or "device",
                                "ip": remote_ip or "",
                                "value": 0,
                            },
                        },
                    )
                )
                # Simple probe fallback (some devices only respond to this shape).
                follow_ups.append(
                    _build_server_command(
                        probe_command,
                        device_identifier,
                        remote_ip=remote_ip,
                        device_type=base_response["type"] or "device",
                        extra={"value": 0},
                    )
                )
            _mark_access_log_probe_sent(terminal)

        job.last_synced_at = timezone.now()
        job.last_status = "success"
        job.last_error = ""
        job.last_payload = {
            "command": command,
            "device_identifier": device_identifier,
            "payload": payload,
            "probe_user": probe_user or {},
            "queued_missing_users": queued_missing_users,
            "approved_user_ids": approved_user_ids,
            "reported_user_ids_available": reported_user_ids_available,
            "user_ids_probe_attempted": already_probed_user_ids or any(
                item.get("cmd") == "getUserInfo" and item.get("value") == 2 for item in follow_ups
            ),
            "access_logs_probe_attempted": already_probed_access_logs or any(
                item.get("cmd") in set(record_probe_commands) for item in follow_ups
            ),
            "access_logs_probe_commands": [item.get("cmd") for item in follow_ups if item.get("cmd") in set(record_probe_commands)],
        }
        job.save(update_fields=["last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])
        print(
            "face-device-sync response command=getUserInfoRet "
            f"device={device_identifier} total={payload.get('total', '<missing>')} "
            f"user_ids={len(payload.get('userIds', [])) if isinstance(payload.get('userIds'), list) else 0} "
            f"user_ids_available={'yes' if reported_user_ids_available else 'no'} "
            f"user_ids_probe_attempted={'yes' if (already_probed_user_ids or any(item.get('cmd') == 'getUserInfo' and item.get('value') == 2 for item in follow_ups)) else 'no'} "
            f"queued_missing_users={queued_missing_users} "
            f"access_logs_probe_attempted={'yes' if (already_probed_access_logs or any(item.get('cmd') in set(record_probe_commands) for item in follow_ups)) else 'no'} "
            f"follow_ups={','.join(item.get('cmd', '<unknown>') for item in follow_ups) or '<none>'}",
            flush=True,
        )
        return WsCommandResult(response={}, follow_ups=_with_action_follow_ups(follow_ups))

    if command == "getRecordRet":
        existing_last_payload = job.last_payload if isinstance(job.last_payload, dict) else {}
        job.last_synced_at = timezone.now()
        job.last_status = "success"
        job.last_error = ""
        job.last_payload = _preserve_probe_flags(
            existing_last_payload,
            {
            "command": command,
            "device_identifier": device_identifier,
            "payload": payload,
            },
        )
        job.save(update_fields=["last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])
        print(
            "face-device-sync response command=getRecordRet "
            f"device={device_identifier} code={payload.get('code', '<missing>')}",
            flush=True,
        )
        return WsCommandResult(response={}, follow_ups=_with_action_follow_ups())

    if command in {"addUserRet", "editUserRet", "createGroupRet", "deleteGroupRet"}:
        user_id = str(payload.get("user_id") or "").strip()
        follow_ups: list[dict[str, Any]] = []
        if _coerce_int(payload.get("code"), default=1) == 0:
            follow_up_command = "getGroups" if command in {"createGroupRet", "deleteGroupRet"} else "getUserInfo"
            follow_up_extra = {} if follow_up_command == "getGroups" else {"value": 2}
            follow_ups.append(
                _build_server_command(
                    follow_up_command,
                    device_identifier,
                    remote_ip=remote_ip,
                    device_type=base_response["type"] or "device",
                    extra=follow_up_extra,
                )
            )
        job.last_synced_at = timezone.now()
        job.last_status = "success" if _coerce_int(payload.get("code"), default=1) == 0 else "error"
        action_label = {
            "addUserRet": "addUser",
            "editUserRet": "editUser",
            "createGroupRet": "createGroup",
            "deleteGroupRet": "deleteGroup",
        }.get(command, command)
        job.last_error = "" if job.last_status == "success" else str(payload.get("msg") or f"{action_label} failed")
        job.last_payload = {
            "command": command,
            "device_identifier": device_identifier,
            "payload": payload,
        }
        job.save(update_fields=["last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])
        print(
            f"face-device-sync response command={command} "
            f"device={device_identifier} code={payload.get('code')} user_id={user_id or '<missing>'} "
            f"msg={payload.get('msg') or '<empty>'} "
            f"follow_ups={','.join(item.get('cmd', '<unknown>') for item in follow_ups) or '<none>'}",
            flush=True,
        )
        return WsCommandResult(response={}, follow_ups=_with_action_follow_ups(follow_ups))

    if command.endswith("Ret"):
        existing_last_payload = job.last_payload if isinstance(job.last_payload, dict) else {}
        job.last_synced_at = timezone.now()
        job.last_status = "success"
        job.last_error = ""
        job.last_payload = _preserve_probe_flags(
            existing_last_payload,
            {
                "command": command,
                "device_identifier": device_identifier,
                "payload": payload,
            },
        )
        job.save(update_fields=["last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])
        print(
            "face-device-sync response command="
            f"{command} device={device_identifier} code={payload.get('code', '<missing>')} follow_ups=<none>",
            flush=True,
        )
        return WsCommandResult(response={}, follow_ups=_with_action_follow_ups())

    if command in {"getUserInfo", "getGroups", "addUser", "editUser", "createGroup", "deleteGroup", "delUser", "delMultiUser"}:
        sync_payload = build_user_sync(device_identifier, cursor=cursor)
        response = dict(base_response)
        if command == "getUserInfo":
            value = payload.get("value")
            try:
                mode = int(value)
            except Exception:
                mode = 0

            response.update(
                {
                    "device_name": device_name,
                    "data": sync_payload,
                    "approved_people": sync_payload["approved_people"],
                    "revoked_people": sync_payload["revoked_people"],
                    "units": sync_payload["units"],
                    "people": sync_payload["approved_people"],
                    "users": sync_payload["approved_people"],
                    "rows": sync_payload["approved_people"],
                    "list": sync_payload["approved_people"],
                    "dataList": sync_payload["approved_people"],
                    "counts": sync_payload["counts"],
                    "truncated": sync_payload["truncated"],
                    "max_items": sync_payload["max_items"],
                    "cursor": sync_payload["cursor"],
                    "next_cursor": sync_payload["next_cursor"],
                }
            )
            if mode in {0, 1}:
                response["total"] = len(sync_payload["approved_people"])
            if mode in {2, 3}:
                response["userIds"] = [str(item.get("user_id") or item.get("id") or "") for item in sync_payload["approved_people"]]
        elif command == "getGroups":
            group_names = sorted(
                {
                    str(item.get("face_group_name") or "").strip()
                    for item in sync_payload["approved_people"]
                    if str(item.get("face_group_name") or "").strip()
                }
            )
            response.update(
                {
                    "device_name": device_name,
                    "groups": group_names,
                    "total": len(group_names),
                }
            )
        elif command == "addUser":
            user_id = str(payload.get("user_id") or "")
            response.update(
                {
                    "msg": "User added successfully" if user_id else "User sync completed",
                    "user_id": user_id,
                    "device_name": device_name,
                    "data": sync_payload,
                }
            )
        elif command == "editUser":
            user_id = str(payload.get("user_id") or "")
            response.update(
                {
                    "msg": "User updated successfully" if user_id else "User update completed",
                    "user_id": user_id,
                    "device_name": device_name,
                    "data": sync_payload,
                }
            )
        elif command == "createGroup":
            group_name = str(payload.get("group_name") or "")
            response.update({"msg": "Group created successfully" if group_name else "Group create completed", "group_name": group_name, "device_name": device_name})
        elif command == "deleteGroup":
            group_name = str(payload.get("group_name") or "")
            response.update({"msg": "Group deleted successfully" if group_name else "Group delete completed", "group_name": group_name, "device_name": device_name})
        elif command == "delUser":
            user_id = str(payload.get("user_id") or "")
            response.update(
                {
                    "msg": "User deleted successfully" if user_id else "User delete completed",
                    "user_id": user_id,
                    "device_name": device_name,
                }
            )
        elif command == "delMultiUser":
            user_ids = payload.get("user_ids")
            if not isinstance(user_ids, list):
                user_ids = []
            response.update(
                {
                    "msg": "Users deleted successfully",
                    "delFailed": [],
                    "user_ids": user_ids,
                    "device_name": device_name,
                }
            )
        job.last_synced_at = timezone.now()
        job.last_status = "success"
        job.last_error = ""
        job.last_payload = response
        if sync_payload["next_cursor"]:
            try:
                job.cursor_at = datetime.fromisoformat(sync_payload["next_cursor"].replace("Z", "+00:00"))
            except Exception:
                pass
        job.save(update_fields=["cursor_at", "last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])
        print(
            "face-device-sync response command="
            f"{command} device={device_identifier} "
            f"approved={len(sync_payload['approved_people'])} "
            f"revoked={len(sync_payload['revoked_people'])} "
            f"units={len(sync_payload['units'])}",
            flush=True,
        )
        return WsCommandResult(response=response, follow_ups=_with_action_follow_ups())

    print(
        "face-device-sync unsupported command "
        f"device={device_identifier} command={command or '<missing>'} payload={_summarize_mapping(payload)}",
        flush=True,
    )
    return WsCommandResult(
        response={
            "command": command or "unknown",
            "success": False,
            "error": f"Unsupported command: {command or '<missing>'}",
            "server_time": _now_iso(),
            "device_identifier": device_identifier,
        },
        follow_ups=_with_action_follow_ups(),
    )
