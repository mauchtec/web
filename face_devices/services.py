from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
from datetime import timedelta, timezone as dt_timezone
from typing import Any
from urllib.parse import unquote
from uuid import UUID
import uuid

from django.core.files.base import ContentFile
from django.db import OperationalError, transaction
from django.utils import timezone

from GateCore.models import GateTerminal, Person
from .models import FaceDeviceAccessLog, FaceDeviceAction, FaceDeviceEvent, FaceDeviceStrangerEvent, FaceDeviceUserState


_INLINE_IMAGE_KEYS = {
    "photo",
    "img",
    "pic",
    "image",
    "picture",
    "snapshot",
    "snapshot_image",
    "face_snapshot",
    "face_image",
    "face_pic",
    "face_photo",
    "face_image_base64",
    "panoramic_image",
    "scene_image",
    "panorama",
    "bg_pic",
    "bg_image",
}


def _looks_like_inline_image(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    text_lc = text.lower()
    if text_lc.startswith("data:image/"):
        return True
    if text_lc.startswith("http://") or text_lc.startswith("https://"):
        return False
    if "%2f9j%2f" in text_lc or "/9j/" in text_lc:
        return True
    if len(text) < 256:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-%")
    sample = text[:1024]
    ratio = sum(1 for ch in sample if ch in allowed) / max(1, len(sample))
    return ratio > 0.96


def _sanitize_payload_for_storage(value: Any, *, key_hint: str = "", depth: int = 0) -> Any:
    if depth > 8:
        return "[omitted_depth]"
    if isinstance(value, dict):
        return {
            str(k): _sanitize_payload_for_storage(v, key_hint=str(k), depth=depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_payload_for_storage(item, key_hint=key_hint, depth=depth + 1) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload_for_storage(item, key_hint=key_hint, depth=depth + 1) for item in value]
    if isinstance(value, str):
        key_lc = (key_hint or "").strip().lower()
        if key_lc in _INLINE_IMAGE_KEYS:
            value_lc = value.strip().lower()
            if value_lc.startswith("http://") or value_lc.startswith("https://"):
                return value
            if _looks_like_inline_image(value) or value.strip():
                return f"[omitted_inline_image len={len(value)}]"
        if len(value) > 4000:
            return f"{value[:4000]}...[truncated len={len(value)}]"
        return value
    return value


def sanitize_face_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    sanitized = _sanitize_payload_for_storage(payload)
    return sanitized if isinstance(sanitized, dict) else {}


def record_face_device_event(
    *,
    terminal: GateTerminal | None,
    device_identifier: str,
    direction: str,
    command: str,
    payload: dict[str, Any] | None = None,
    status: str = "received",
    remote_ip: str | None = None,
    error: str = "",
) -> FaceDeviceEvent:
    return FaceDeviceEvent.objects.create(
        terminal=terminal,
        device_identifier=device_identifier,
        direction=direction,
        command=(command or "unknown")[:120],
        status=status,
        payload=sanitize_face_payload(payload),
        remote_ip=remote_ip,
        error=(error or "")[:4000],
    )


def queue_face_device_action(
    *,
    terminal: GateTerminal,
    action: str,
    request_payload: dict[str, Any] | None,
    requested_by: Any = None,
) -> FaceDeviceAction:
    return FaceDeviceAction.objects.create(
        terminal=terminal,
        device_identifier=terminal.serial_number,
        action=action,
        status="pending",
        request_payload=request_payload or {},
        requested_by=requested_by if getattr(requested_by, "is_authenticated", False) else None,
    )


def _command_for_action(action: FaceDeviceAction, *, remote_ip: str | None, device_type: str) -> dict[str, Any] | None:
    payload = action.request_payload if isinstance(action.request_payload, dict) else {}

    command: dict[str, Any] | None = None
    if action.action == "pull_settings":
        command = {"cmd": "getDeviceSettings", "settings": ["all"]}
    elif action.action == "pull_user_count":
        command = {"cmd": "getUserInfo", "value": 0}
    elif action.action == "pull_user_ids":
        command = {"cmd": "getUserInfo", "value": 2}
    elif action.action == "pull_groups":
        command = {"cmd": "getGroups"}
    elif action.action == "pull_access_logs":
        command = {"cmd": "getRecord", **payload}
        command.setdefault("value", 0)
    elif action.action == "sync_users":
        command = {"cmd": "getUserInfo", "value": 2}
    elif action.action == "add_user":
        command = {"cmd": "addUser", **payload}
    elif action.action == "edit_user":
        user_id = str(payload.get("user_id") or "").strip()
        if user_id:
            command = {"cmd": "editUser", **payload}
    elif action.action == "create_group":
        group_name = str(payload.get("group_name") or payload.get("face_group_name") or "").strip()
        if group_name:
            command = {"cmd": "createGroup", "group_name": group_name}
    elif action.action == "delete_group":
        group_name = str(payload.get("group_name") or payload.get("face_group_name") or "").strip()
        if group_name:
            command = {"cmd": "deleteGroup", "group_name": group_name}
    elif action.action == "delete_user":
        user_id = str(payload.get("user_id") or "").strip()
        if user_id:
            command = {"cmd": "delUser", "user_id": user_id}
    elif action.action == "delete_all_users":
        command = {"cmd": "delAllUser"}
    elif action.action == "open_door":
        command = {"cmd": "setDoor", "value": str(payload.get("value") or "on").strip() or "on"}
    elif action.action == "reboot":
        command = {"cmd": "reboot"}
    elif action.action == "ping":
        command = {"cmd": "ping"}

    if not command:
        return None
    command.setdefault("sn", action.device_identifier)
    command.setdefault("timestamp", int(timezone.now().timestamp()))
    command.setdefault("type", device_type or "device")
    if remote_ip:
        command.setdefault("ip", remote_ip)
    command["__action_id"] = str(action.id)
    return command


def dequeue_pending_actions(
    *,
    terminal: GateTerminal | None,
    device_identifier: str,
    remote_ip: str | None,
    device_type: str,
) -> list[dict[str, Any]]:
    now = timezone.now()
    with transaction.atomic():
        stale_running = FaceDeviceAction.objects.select_for_update().filter(
            device_identifier=device_identifier,
            status="running",
            started_at__lt=now - timedelta(minutes=3),
        )
        for item in stale_running:
            item.status = "timeout"
            item.completed_at = now
            item.error = "Timed out waiting for device response."
            item.save(update_fields=["status", "completed_at", "error", "modified_at"])

        pending = list(
            FaceDeviceAction.objects.select_for_update()
            .filter(device_identifier=device_identifier, status="pending")
            .order_by("created_at")[:5]
        )

        commands: list[dict[str, Any]] = []
        for action in pending:
            command = _command_for_action(action, remote_ip=remote_ip, device_type=device_type)
            if command is None:
                action.status = "error"
                action.completed_at = now
                action.error = "Action payload is incomplete or unsupported."
                action.save(update_fields=["status", "completed_at", "error", "modified_at"])
                continue
            action.status = "running"
            action.started_at = now
            action.error = ""
            action.save(update_fields=["status", "started_at", "error", "modified_at"])
            commands.append(command)
    return commands


def _parse_action_id(extra_value: Any) -> UUID | None:
    if not isinstance(extra_value, str) or not extra_value.strip():
        return None
    try:
        return UUID(extra_value.strip())
    except Exception:
        return None


def resolve_action_result(
    *,
    device_identifier: str,
    payload: dict[str, Any],
    command: str,
) -> FaceDeviceAction | None:
    expected_response_by_action = {
        "ping": {"ping", "heartbeat"},
        "pull_settings": {"getDeviceSettingsRet"},
        "pull_user_count": {"getUserInfoRet"},
        "pull_user_ids": {"getUserInfoRet"},
        "pull_groups": {"getGroupsRet"},
        "sync_users": {"getUserInfoRet", "addUserRet"},
        "pull_access_logs": {"getRecordRet", "getAccessRecordRet", "getPassRecordRet"},
        "add_user": {"addUserRet"},
        "edit_user": {"editUserRet"},
        "create_group": {"createGroupRet"},
        "delete_group": {"deleteGroupRet"},
        "delete_user": {"delUserRet"},
        "delete_all_users": {"delAllUserRet"},
        "open_door": {"setDoorRet"},
        "reboot": {"rebootRet"},
    }

    action_id = _parse_action_id(payload.get("extra"))
    if action_id:
        action = FaceDeviceAction.objects.filter(id=action_id, device_identifier=device_identifier).first()
    else:
        running = list(
            FaceDeviceAction.objects.filter(device_identifier=device_identifier, status="running")
            .order_by("-started_at")[:10]
        )
        action = None
        for item in running:
            expected = expected_response_by_action.get(item.action, set())
            if command in expected:
                action = item
                break
    if not action:
        return None

    expected_for_selected = expected_response_by_action.get(action.action, set())
    if expected_for_selected and command not in expected_for_selected:
        return None

    code = payload.get("code")
    try:
        is_success = int(code) == 0
    except Exception:
        is_success = command in {"ping", "heartbeat"}

    action.status = "success" if is_success else "error"
    action.completed_at = timezone.now()
    action.response_payload = payload
    action.error = "" if is_success else str(payload.get("msg") or payload.get("error") or "Action failed")
    action.save(update_fields=["status", "completed_at", "response_payload", "error", "modified_at"])
    return action


_IGNORED_ACCESS_COMMANDS = {
    "",
    "declare",
    "declareRet",
    "ping",
    "heartbeat",
    "getDeviceSettings",
    "getDeviceSettingsRet",
    "getUserInfo",
    "getUserInfoRet",
    "getGroups",
    "getGroupsRet",
    "addUser",
    "addUserRet",
    "editUser",
    "editUserRet",
    "setDoor",
    "setDoorRet",
    "delUser",
    "delUserRet",
    "delAllUser",
    "delAllUserRet",
    "to_device",
}

_PASS_VALUES = {"1", "true", "pass", "allow", "allowed", "ok", "success", "succeeded", "open", "granted", "through"}
_DENY_VALUES = {"0", "false", "deny", "denied", "reject", "rejected", "blocked", "fail", "failed", "forbidden"}
_UNKNOWN_VALUES = {"unknown", "stranger", "visitor", "unregistered", "no_match", "nomatch"}


def _normalize_key_name(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _payload_value(payload: dict[str, Any], aliases: list[str]) -> Any:
    for alias in aliases:
        if alias in payload:
            return payload.get(alias)
    normalized_payload = {_normalize_key_name(key): val for key, val in payload.items()}
    for alias in aliases:
        normalized_alias = _normalize_key_name(alias)
        if normalized_alias and normalized_alias in normalized_payload:
            return normalized_payload.get(normalized_alias)
    return None


def _event_time_from_payload(payload: dict[str, Any]) -> timezone.datetime:
    for key in (
        "event_time",
        "record_time",
        "recog_time",
        "recognition_time",
        "recognition time",
        "time",
        "verify_time",
        "timestamp",
        "ts",
        "create_time",
        "check_time",
    ):
        value = _payload_value(payload, [key])
        if value in (None, ""):
            continue
        if isinstance(value, (int, float)):
            seconds = float(value) / 1000.0 if float(value) > 9999999999 else float(value)
            try:
                return timezone.datetime.fromtimestamp(seconds, tz=dt_timezone.utc)
            except Exception:
                continue
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                continue
            if raw.isdigit():
                try:
                    num = int(raw)
                    seconds = num / 1000.0 if num > 9999999999 else num
                    return timezone.datetime.fromtimestamp(seconds, tz=dt_timezone.utc)
                except Exception:
                    continue
            try:
                parsed = timezone.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else timezone.make_aware(parsed, dt_timezone.utc)
            except Exception:
                continue
    return timezone.now()


def _normalize_result(payload: dict[str, Any]) -> str:
    for key in ("result", "verify_result", "open_door_result", "pass_result", "status", "pass", "is_pass", "open_result", "auth_result", "pass_status"):
        value = _payload_value(payload, [key])
        if value in (None, ""):
            continue
        text = str(value).strip().lower()
        if text in _PASS_VALUES:
            return "pass"
        if text in _DENY_VALUES:
            return "deny"
        if text in _UNKNOWN_VALUES:
            return "unknown"
    if _looks_like_stranger_payload(payload):
        return "unknown"
    code = _payload_value(payload, ["code"])
    try:
        return "pass" if int(code) == 0 else "deny"
    except Exception:
        return "unknown"


def _normalize_confidence(payload: dict[str, Any]) -> Decimal | None:
    for key in ("confidence", "score", "similarity", "match_score", "face_score"):
        value = _payload_value(payload, [key])
        if value in (None, ""):
            continue
        try:
            score = Decimal(str(value))
            return score.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            continue
    return None


def _normalize_liveness_score(payload: dict[str, Any]) -> Decimal | None:
    for key in ("liveness_score", "liveness", "live_score", "livenessscore"):
        value = _payload_value(payload, [key])
        if value in (None, ""):
            continue
        try:
            score = Decimal(str(value))
            return score.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            continue
    return None


def _first_non_empty(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = _payload_value(payload, [key])
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _looks_like_stranger_payload(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in (
        "stranger",
        "is_stranger",
        "unknown_person",
        "stranger_id",
        "strangerId",
        "stranger_id_no",
    ):
        value = _payload_value(payload, [key])
        if value in (None, ""):
            continue
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "unknown", "stranger"}:
            return True
    for key in ("user_name", "name", "person_name", "result", "status", "recognition_result"):
        value = _payload_value(payload, [key])
        if str(value or "").strip().lower() in _UNKNOWN_VALUES:
            return True
    if _payload_value(payload, ["face_image", "face_image_base64"]) not in (None, "") and _first_non_empty(
        payload,
        ["user_id", "user id", "userid", "uid", "person_id", "subject_id", "face_subject_id"],
    ) == "":
        return True
    return False


def _resolve_person(payload: dict[str, Any]) -> Person | None:
    face_subject_id = _first_non_empty(
        payload,
        ["user_id", "user id", "userid", "uid", "user_number", "person_id", "subject_id", "face_subject_id"],
    )
    if face_subject_id:
        person = Person.objects.filter(face_subject_id=face_subject_id).first()
        if person:
            return person
    person_id = _first_non_empty(payload, ["person_uuid", "person"])
    if person_id:
        person = Person.objects.filter(id=person_id).first()
        if person:
            return person
    id_number = _first_non_empty(payload, ["id_number", "id_card", "ID card number", "id card number"])
    if id_number:
        person = Person.objects.filter(id_number=id_number).first()
        if person:
            return person
    phone = _first_non_empty(payload, ["phone", "mobile", "Cellphone number", "cellphone number", "cell phone number"])
    if phone:
        person = Person.objects.filter(phone=phone).first()
        if person:
            return person
    card_number = _first_non_empty(payload, ["card_number", "Ic", "ic"])
    if card_number:
        person = Person.objects.filter(card_number=card_number).first()
        if person:
            return person
    return None


def _decode_image_content(value: Any, fallback_prefix: str) -> tuple[str, ContentFile] | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = unquote(raw)
    if raw.startswith("http://") or raw.startswith("https://"):
        return None

    ext = "jpg"
    b64_data = raw
    if raw.startswith("data:image/") and ";base64," in raw:
        header, b64_data = raw.split(",", 1)
        type_hint = header.split(";")[0].split("/", 1)[-1].strip().lower()
        if type_hint in {"jpeg", "jpg", "png", "webp"}:
            ext = "jpg" if type_hint == "jpeg" else type_hint

    try:
        decoded = base64.b64decode(b64_data, validate=False)
    except Exception:
        return None
    if not decoded:
        return None

    name = f"{fallback_prefix}_{uuid.uuid4().hex[:16]}.{ext}"
    return name, ContentFile(decoded, name=name)


def _extract_access_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(payload.get("logs"), list):
        candidates.extend(item for item in payload["logs"] if isinstance(item, dict))
    if isinstance(payload.get("records"), list):
        candidates.extend(item for item in payload["records"] if isinstance(item, dict))
    if isinstance(payload.get("record"), dict):
        candidates.append(payload["record"])
    data = payload.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("records"), list):
            candidates.extend(item for item in data["records"] if isinstance(item, dict))
        if isinstance(data.get("record"), dict):
            candidates.append(data["record"])
        if any(k in data for k in ("user_id", "result", "snapshot", "face_snapshot", "confidence", "liveness_score", "face_image", "face_group_name")):
            candidates.append(data)
    if isinstance(data, list):
        candidates.extend(item for item in data if isinstance(item, dict))
    for nested_key in ("body", "result", "info"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            if isinstance(nested.get("records"), list):
                candidates.extend(item for item in nested["records"] if isinstance(item, dict))
            if any(k in nested for k in ("user_id", "result", "snapshot", "face_snapshot", "confidence", "img", "pic", "image", "liveness_score", "face_image", "face_group_name")):
                candidates.append(nested)
    if not candidates:
        candidates.append(payload)
    return candidates


def _credential_details(payload: dict[str, Any]) -> tuple[str, str]:
    qr_value = _first_non_empty(payload, ["qr_code", "qrcode", "qr", "barcode", "scan_data", "code"])
    if qr_value and not qr_value.isdigit():
        return "qr", qr_value
    card_value = _first_non_empty(payload, ["card_number", "Ic", "ic", "card", "card_no"])
    if card_value:
        return "card", card_value
    pin_value = _first_non_empty(payload, ["pin", "password"])
    if pin_value:
        return "pin", pin_value
    return "", ""


def _sync_stranger_event(row: FaceDeviceAccessLog) -> None:
    if not row or row.result != "unknown" or row.person_id:
        return
    payload = row.payload if isinstance(row.payload, dict) else {}
    credential_type, credential_value = _credential_details(payload)
    defaults = {
        "terminal": row.terminal,
        "device_identifier": row.device_identifier,
        "source_command": row.source_command,
        "event_time": row.event_time,
        "confidence": row.confidence,
        "liveness_score": _normalize_liveness_score(payload),
        "credential_type": credential_type,
        "credential_value": credential_value[:200],
        "face_group_name": _first_non_empty(payload, ["face_group_name", "group_name", "group"])[:120],
        "payload": payload,
        "remote_ip": row.remote_ip,
        "status": "new",
    }
    stranger_event, created = FaceDeviceStrangerEvent.objects.get_or_create(access_log=row, defaults=defaults)
    if created:
        if row.snapshot_image:
            stranger_event.snapshot_image = row.snapshot_image
        if row.panoramic_image:
            stranger_event.panoramic_image = row.panoramic_image
        stranger_event.save(update_fields=["snapshot_image", "panoramic_image", "modified_at"])
        return
    update_fields: list[str] = []
    for key, value in defaults.items():
        if key == "status" and stranger_event.status != "new":
            continue
        if getattr(stranger_event, key) != value:
            setattr(stranger_event, key, value)
            update_fields.append(key)
    if row.snapshot_image and not stranger_event.snapshot_image:
        stranger_event.snapshot_image = row.snapshot_image
        update_fields.append("snapshot_image")
    if row.panoramic_image and not stranger_event.panoramic_image:
        stranger_event.panoramic_image = row.panoramic_image
        update_fields.append("panoramic_image")
    if update_fields:
        stranger_event.save(update_fields=[*update_fields, "modified_at"])


def _access_dedupe_signature(
    *,
    device_identifier: str,
    command: str,
    event_time: timezone.datetime,
    candidate: dict[str, Any],
    result: str,
    remote_ip: str | None,
) -> tuple[str, str, str, str, str, str, str, str]:
    user_id = _first_non_empty(candidate, ["user_id", "uid", "user_number", "person_id", "subject_id", "face_subject_id"])
    user_name = _first_non_empty(candidate, ["user_name", "name", "person_name"])
    recog_time = _first_non_empty(candidate, ["recog_time", "event_time", "record_time", "verify_time", "timestamp", "ts"])
    pass_status = _first_non_empty(candidate, ["pass_status", "status", "pass", "is_pass"])
    recog_type = _first_non_empty(candidate, ["recog_type", "type"])
    second_bucket = event_time.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat()
    return (
        str(device_identifier or "").strip(),
        str(command or "").strip(),
        second_bucket,
        str(result or "").strip(),
        str(user_id or "").strip(),
        str(user_name or "").strip(),
        str(recog_time or "").strip(),
        f"{str(pass_status or '').strip()}|{str(recog_type or '').strip()}|{str(remote_ip or '').strip()}",
    )


def _is_recent_duplicate_access_log(
    *,
    device_identifier: str,
    command: str,
    event_time: timezone.datetime,
    candidate: dict[str, Any],
    result: str,
    remote_ip: str | None,
) -> bool:
    signature = _access_dedupe_signature(
        device_identifier=device_identifier,
        command=command,
        event_time=event_time,
        candidate=candidate,
        result=result,
        remote_ip=remote_ip,
    )
    start_at = event_time - timedelta(seconds=2)
    end_at = event_time + timedelta(seconds=2)
    recent_rows = FaceDeviceAccessLog.objects.filter(
        device_identifier=device_identifier,
        source_command=command[:120],
        event_time__gte=start_at,
        event_time__lte=end_at,
        result=result,
    ).order_by("-event_time")[:20]
    for row in recent_rows:
        existing_payload = row.payload if isinstance(row.payload, dict) else {}
        existing_sig = _access_dedupe_signature(
            device_identifier=row.device_identifier,
            command=row.source_command,
            event_time=row.event_time or event_time,
            candidate=existing_payload,
            result=row.result,
            remote_ip=row.remote_ip,
        )
        if existing_sig == signature:
            return True
    return False


def ingest_face_device_access_log(
    *,
    terminal: GateTerminal | None,
    device_identifier: str,
    command: str,
    payload: dict[str, Any],
    remote_ip: str | None = None,
) -> list[FaceDeviceAccessLog]:
    command_clean = str(command or "").strip()
    if command_clean in _IGNORED_ACCESS_COMMANDS:
        return []

    command_lc = command_clean.lower()
    hinted = any(token in command_lc for token in ("record", "access", "recogn", "verify", "pass", "open", "stranger", "snapshot", "photo", "door", "qr", "card", "scan"))
    created: list[FaceDeviceAccessLog] = []
    in_request_seen: set[tuple[str, str, str, str, str, str, str, str]] = set()
    for raw_candidate in _extract_access_candidates(payload):
        candidate = raw_candidate if isinstance(raw_candidate, dict) else {}
        has_identity = any(
            _payload_value(candidate, [key]) not in (None, "")
            for key in ("user_id", "user id", "userid", "uid", "id_number", "id_card", "ID card number", "card_number", "Ic", "ic", "person", "qr_code", "qrcode", "barcode")
        )
        has_signal = any(
            _payload_value(candidate, [key]) not in (None, "")
            for key in (
                "result",
                "verify_result",
                "status",
                "pass",
                "is_pass",
                "pass_status",
                "snapshot",
                "snapshot_image",
                "face_snapshot",
                "face_image",
                "panoramic_image",
                "scene_image",
                "img",
                "pic",
                "image",
                "picture",
                "face_pic",
                "face_image_base64",
                "face_photo",
                "open_result",
                "auth_result",
                "recognition_time",
                "recognition time",
                "recog_time",
                "confidence",
                "liveness_score",
                "face_group_name",
                "face_image",
                "qr_code",
                "qrcode",
                "barcode",
                "scan_data",
                "card_number",
                "Ic",
                "ic",
            )
        )
        if not hinted and not (has_identity and has_signal):
            continue

        event_time = _event_time_from_payload(candidate)
        result = _normalize_result(candidate)
        if "stranger" in command_lc and result == "pass":
            result = "unknown"
        if result == "unknown" and command_lc in {"getrecordret", "getaccessrecordret", "getpassrecordret"}:
            if has_identity and has_signal and not _looks_like_stranger_payload(candidate):
                result = "pass"
        dedupe_sig = _access_dedupe_signature(
            device_identifier=device_identifier,
            command=command_clean,
            event_time=event_time,
            candidate=candidate,
            result=result,
            remote_ip=remote_ip,
        )
        if dedupe_sig in in_request_seen:
            continue
        in_request_seen.add(dedupe_sig)
        if _is_recent_duplicate_access_log(
            device_identifier=device_identifier,
            command=command_clean,
            event_time=event_time,
            candidate=candidate,
            result=result,
            remote_ip=remote_ip,
        ):
            continue

        row = FaceDeviceAccessLog(
            terminal=terminal,
            person=_resolve_person(candidate),
            device_identifier=device_identifier,
            source_command=command_clean[:120],
            event_time=event_time,
            result=result,
            confidence=_normalize_confidence(candidate),
            payload=sanitize_face_payload(candidate),
            remote_ip=remote_ip,
        )

        snapshot = _decode_image_content(
            _payload_value(
                candidate,
                [
                    "snapshot",
                    "snapshot_image",
                    "face_snapshot",
                    "face_image",
                    "face_image_base64",
                    "face_pic",
                    "face_photo",
                    "image",
                    "img",
                    "pic",
                    "picture",
                    "photo",
                ],
            ),
            "face_snapshot",
        )
        if snapshot:
            name, content = snapshot
            row.snapshot_image.save(name, content, save=False)

        panoramic = _decode_image_content(
            _payload_value(
                candidate,
                [
                    "panoramic_image",
                    "scene_image",
                    "panorama",
                    "bg_pic",
                    "bg_image",
                ],
            ),
            "face_panoramic",
        )
        if panoramic:
            name, content = panoramic
            row.panoramic_image.save(name, content, save=False)

        row.save()
        created.append(row)
        _sync_stranger_event(row)
        _apply_visitor_face_grant_from_access_log(row)
    return created


def _apply_visitor_face_grant_from_access_log(row: FaceDeviceAccessLog) -> None:
    if not row or row.result != "pass" or not row.person_id or not row.terminal_id:
        return

    terminal = row.terminal
    if not terminal or terminal.direction not in {"entry", "exit"}:
        return

    try:
        from GateCore.models import VisitorFaceAccessGrant
    except Exception:
        return

    try:
        grant = (
            VisitorFaceAccessGrant.objects.select_related("guest_registration", "entry_terminal", "exit_terminal")
            .filter(
                person=row.person,
                status__in=["approved", "active"],
                valid_from__lte=row.event_time,
                valid_until__gte=row.event_time,
            )
            .order_by("-created_at")
            .first()
        )
    except OperationalError:
        return

    if not grant:
        return

    _consume_visitor_face_grant_pass(grant, row)


def _consume_visitor_face_grant_pass(grant, row: FaceDeviceAccessLog) -> None:
    terminal = row.terminal
    if not terminal:
        return

    try:
        from GateCore.api_views.device_sync import queue_face_device_delete_user
    except Exception:
        queue_face_device_delete_user = None

    now = row.event_time or timezone.now()
    update_fields: list[str] = []
    queued_delete = False
    delete_terminals = []
    disable_facial_after_consume = False
    consumed_person = None

    with transaction.atomic():
        locked = type(grant).objects.select_for_update().select_related("guest_registration", "entry_terminal", "exit_terminal").get(id=grant.id)

        if terminal.direction == "entry":
            if not locked.entry_terminal_id or str(locked.entry_terminal_id) != str(terminal.id) or locked.entry_pass_used:
                return
            locked.entry_pass_used = True
            locked.entry_used_at = now
            update_fields.extend(["entry_pass_used", "entry_used_at"])
            guest = locked.guest_registration
            if guest and guest.actual_arrival is None:
                guest.actual_arrival = now
                guest.save(update_fields=["actual_arrival", "modified_at"])
        elif terminal.direction == "exit":
            if not locked.exit_terminal_id or str(locked.exit_terminal_id) != str(terminal.id) or locked.exit_pass_used:
                return
            locked.exit_pass_used = True
            locked.exit_used_at = now
            update_fields.extend(["exit_pass_used", "exit_used_at"])
            guest = locked.guest_registration
            if guest and guest.actual_departure is None:
                guest.actual_departure = now
                guest.save(update_fields=["actual_departure", "modified_at"])
        else:
            return

        if locked.is_fully_consumed:
            locked.status = "completed"
            locked.revoked_at = now
            update_fields.extend(["status", "revoked_at"])

        if update_fields:
            locked.save(update_fields=[*update_fields, "modified_at"])
            queued_delete = True
            consumed_person = locked.person
            if locked.is_fully_consumed:
                # Final pass consumed: force-remove from all assigned terminals.
                delete_terminals = [locked.entry_terminal, locked.exit_terminal]
                disable_facial_after_consume = True
            else:
                delete_terminals = [terminal]

    if queued_delete and queue_face_device_delete_user:
        seen_terminal_ids = set()
        for target_terminal in delete_terminals:
            terminal_id = str(getattr(target_terminal, "id", "") or "").strip()
            if not target_terminal or not terminal_id or terminal_id in seen_terminal_ids:
                continue
            queue_face_device_delete_user(target_terminal, row.person)
            seen_terminal_ids.add(terminal_id)

    if disable_facial_after_consume and consumed_person and consumed_person.facial_recognition_enabled:
        has_other_active_grant = type(grant).objects.filter(
            person=consumed_person,
            status__in=["approved", "active"],
            valid_until__gte=timezone.now(),
        ).exclude(id=grant.id).exists()
        if not has_other_active_grant:
            consumed_person.facial_recognition_enabled = False
            consumed_person.save(update_fields=["facial_recognition_enabled", "modified_at"])


def cleanup_expired_visitor_face_grants(*, dry_run: bool = False) -> dict[str, int]:
    try:
        from GateCore.models import VisitorFaceAccessGrant
    except Exception:
        return {"expired_grants": 0, "delete_actions_queued": 0, "people_disabled": 0, "dry_run": dry_run}

    now = timezone.now()
    try:
        expired = list(
            VisitorFaceAccessGrant.objects.select_related("person", "entry_terminal", "exit_terminal")
            .filter(
                status__in=["approved", "active"],
                valid_until__lt=now,
            )
            .order_by("valid_until", "created_at")
        )
    except OperationalError:
        return {"expired_grants": 0, "delete_actions_queued": 0, "people_disabled": 0, "dry_run": dry_run}

    delete_actions_queued = 0
    people_disabled = 0

    try:
        from GateCore.api_views.device_sync import queue_face_device_delete_user
    except Exception:
        queue_face_device_delete_user = None

    for grant in expired:
        person = grant.person
        if not dry_run and queue_face_device_delete_user:
            seen_terminal_ids = set()
            for target_terminal in (grant.entry_terminal, grant.exit_terminal):
                terminal_id = str(getattr(target_terminal, "id", "") or "").strip()
                if not target_terminal or not terminal_id or terminal_id in seen_terminal_ids:
                    continue
                if queue_face_device_delete_user(target_terminal, person):
                    delete_actions_queued += 1
                seen_terminal_ids.add(terminal_id)

        if not dry_run:
            grant.status = "expired"
            grant.revoked_at = now
            suffix = f"Auto-expired at {now.isoformat()}."
            grant.notes = f"{grant.notes}\n{suffix}".strip() if grant.notes else suffix
            grant.save(update_fields=["status", "revoked_at", "notes", "modified_at"])

            other_active_exists = type(grant).objects.filter(
                person=person,
                status__in=["approved", "active"],
                valid_until__gte=now,
            ).exclude(id=grant.id).exists()
            if person and person.facial_recognition_enabled and not other_active_exists:
                person.facial_recognition_enabled = False
                person.save(update_fields=["facial_recognition_enabled", "modified_at"])
                people_disabled += 1

    return {
        "expired_grants": len(expired),
        "delete_actions_queued": delete_actions_queued,
        "people_disabled": people_disabled,
        "dry_run": dry_run,
    }


def refresh_face_device_user_state(
    *,
    terminal: GateTerminal | None,
    device_identifier: str,
    approved_user_ids: list[str],
    reported_user_ids: list[str],
    payload: dict[str, Any] | None = None,
) -> dict[str, int]:
    approved_set = {str(item).strip() for item in approved_user_ids if str(item).strip()}
    reported_set = {str(item).strip() for item in reported_user_ids if str(item).strip()}
    all_ids = approved_set | reported_set
    now = timezone.now()

    people_map: dict[str, Person] = {
        row.face_subject_id: row
        for row in Person.objects.filter(face_subject_id__in=all_ids).exclude(face_subject_id="")
    }

    with transaction.atomic():
        existing = {
            row.user_identifier: row
            for row in FaceDeviceUserState.objects.select_for_update().filter(device_identifier=device_identifier)
        }

        stale_ids = set(existing.keys()) - all_ids
        if stale_ids:
            FaceDeviceUserState.objects.filter(
                device_identifier=device_identifier,
                user_identifier__in=stale_ids,
            ).update(
                state="stale",
                payload=payload or {},
                modified_at=now,
            )

        for user_identifier in sorted(all_ids):
            if user_identifier in approved_set and user_identifier in reported_set:
                state = "present"
            elif user_identifier in approved_set:
                state = "missing"
            else:
                state = "unexpected"
            row = existing.get(user_identifier)
            if row:
                row.state = state
                row.terminal = terminal
                row.person = people_map.get(user_identifier)
                row.payload = payload or {}
                if user_identifier in reported_set:
                    row.last_seen_on_device_at = now
                row.save(
                    update_fields=[
                        "state",
                        "terminal",
                        "person",
                        "payload",
                        "last_seen_on_device_at",
                        "modified_at",
                    ]
                )
                continue
            FaceDeviceUserState.objects.create(
                terminal=terminal,
                person=people_map.get(user_identifier),
                device_identifier=device_identifier,
                user_identifier=user_identifier,
                state=state,
                last_seen_on_device_at=now if user_identifier in reported_set else None,
                payload=payload or {},
            )

    return {
        "approved_count": len(approved_set),
        "reported_count": len(reported_set),
        "missing_count": len(approved_set - reported_set),
        "unexpected_count": len(reported_set - approved_set),
        "present_count": len(approved_set & reported_set),
    }
