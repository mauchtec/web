import csv
import io
import json
import os
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from GateCore.models import DeviceSyncJob, GateTerminal, Person
from GateCore.services.photo_quality import describe_uploaded_photo
from .models import FaceDeviceAccessLog, FaceDeviceAction, FaceDeviceEvent, FaceDeviceStrangerEvent, FaceDeviceUserState
from .services import ingest_face_device_access_log, queue_face_device_action, sanitize_face_payload

DESTRUCTIVE_ACTIONS = {"delete_user", "delete_all_users", "reboot"}


def _normalize_key_name(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _payload_value(payload: dict, aliases: list[str]) -> str:
    for alias in aliases:
        value = payload.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    normalized_payload = {_normalize_key_name(k): v for k, v in payload.items()}
    for alias in aliases:
        key = _normalize_key_name(alias)
        if key and normalized_payload.get(key) not in (None, ""):
            return str(normalized_payload.get(key)).strip()
    return ""


def _normalize_csv_header(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _csv_row_value(row: dict, aliases: list[str]) -> str:
    for alias in aliases:
        value = row.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    normalized = {_normalize_csv_header(k): v for k, v in row.items()}
    for alias in aliases:
        key = _normalize_csv_header(alias)
        value = normalized.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _read_tabular_upload(filename: str, raw_bytes: bytes) -> tuple[list[dict], list[str], str]:
    extension = os.path.splitext(str(filename or ""))[1].lower()

    if extension in {".csv", ".txt", ""}:
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return [], [], "CSV has no headers."
        rows = [dict(row or {}) for row in reader]
        return rows, list(reader.fieldnames or []), ""

    if extension == ".xls":
        try:
            import xlrd  # type: ignore
        except Exception:
            return [], [], "XLS import requires 'xlrd'. Please install dependency or export CSV."
        try:
            workbook = xlrd.open_workbook(file_contents=raw_bytes)
            if workbook.nsheets <= 0:
                return [], [], "XLS has no sheets."
            sheet = workbook.sheet_by_index(0)
            if sheet.nrows <= 0:
                return [], [], "XLS sheet is empty."
            headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
            rows: list[dict] = []
            for row_idx in range(1, sheet.nrows):
                row_data: dict = {}
                for col_idx, header in enumerate(headers):
                    if not header:
                        continue
                    value = sheet.cell_value(row_idx, col_idx)
                    if isinstance(value, float) and value.is_integer():
                        value = int(value)
                    row_data[header] = str(value).strip()
                rows.append(row_data)
            return rows, headers, ""
        except Exception as exc:
            return [], [], f"Unable to parse XLS file: {exc}"

    if extension == ".xlsx":
        try:
            import pandas as pd  # type: ignore
        except Exception:
            return [], [], "XLSX import requires 'pandas' and 'openpyxl'. Please export CSV."
        try:
            frame = pd.read_excel(io.BytesIO(raw_bytes), dtype=str).fillna("")
            headers = [str(col).strip() for col in frame.columns]
            rows = [{str(k).strip(): str(v).strip() for k, v in row.items()} for row in frame.to_dict(orient="records")]
            return rows, headers, ""
        except Exception as exc:
            return [], [], f"Unable to parse XLSX file: {exc}"

    return [], [], f"Unsupported file type '{extension}'. Use CSV, XLS, or XLSX."


def _import_decision(pass_status_raw: str, result_raw: str, user_name: str, confidence_raw: str) -> tuple[int, str]:
    status_text = str(pass_status_raw or "").strip().lower()
    result_text = str(result_raw or "").strip().lower()

    if status_text in {"1", "true", "yes", "y", "pass", "passed", "granted", "allow", "allowed"}:
        return 1, "pass"
    if status_text in {"0", "false", "no", "n", "deny", "denied", "blocked", "reject", "rejected"}:
        return 0, "deny"

    if result_text in {"pass", "passed", "granted", "allow", "allowed", "success"}:
        return 1, "pass"
    if result_text in {"deny", "denied", "blocked", "reject", "rejected", "fail", "failed"}:
        return 0, "deny"
    if result_text in {"unknown", "stranger", "visitor"}:
        return 0, "unknown"

    confidence_text = str(confidence_raw or "").strip()
    try:
        confidence_value = float(confidence_text) if confidence_text else 0.0
    except Exception:
        confidence_value = 0.0

    if str(user_name or "").strip().lower() == "visitor" and confidence_value <= 0.0:
        return 0, "unknown"

    return 0, "unknown"


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _can_run_destructive_action(request) -> bool:
    user = request.user
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.has_perm("face_devices.can_run_destructive_face_device_actions")
        )
    )


def _validate_action_payload(action: str, payload: dict) -> str:
    if action == "delete_user":
        if not str(payload.get("user_id") or "").strip():
            return "payload.user_id is required for delete_user"
        return ""

    if action == "add_user":
        required_keys = {"user_id", "id_name", "name", "face_template"}
        missing = [item for item in sorted(required_keys) if not str(payload.get(item) or "").strip()]
        if missing:
            return f"payload missing required keys for add_user: {', '.join(missing)}"
        user_id = str(payload.get("user_id") or "").strip()
        if len(user_id) > 120:
            return "payload.user_id must be <= 120 characters"
        face_template = str(payload.get("face_template") or "").strip()
        if len(face_template) < 50:
            return "payload.face_template looks too short"
        if len(face_template) > 6_000_000:
            return "payload.face_template is too large"
        for key in ("name", "id_name", "tts_name"):
            if key in payload and len(str(payload.get(key) or "").strip()) > 200:
                return f"payload.{key} must be <= 200 characters"
        for key in ("id_number", "id_card", "phone", "Ic"):
            if key in payload and len(str(payload.get(key) or "").strip()) > 120:
                return f"payload.{key} must be <= 120 characters"
        return ""

    if action == "edit_user":
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            return "payload.user_id is required for edit_user"
        if len(user_id) > 120:
            return "payload.user_id must be <= 120 characters"
        if "face_template" in payload:
            face_template = str(payload.get("face_template") or "").strip()
            if len(face_template) < 50:
                return "payload.face_template looks too short"
            if len(face_template) > 6_000_000:
                return "payload.face_template is too large"
        for key in ("name", "id_name", "tts_name"):
            if key in payload and len(str(payload.get(key) or "").strip()) > 200:
                return f"payload.{key} must be <= 200 characters"
        for key in ("id_number", "id_card", "phone", "Ic"):
            if key in payload and len(str(payload.get(key) or "").strip()) > 120:
                return f"payload.{key} must be <= 120 characters"
        return ""

    if action in {"pull_settings", "pull_user_count", "pull_user_ids", "pull_groups", "sync_users", "delete_all_users", "reboot", "ping"}:
        return ""

    if action in {"create_group", "delete_group"}:
        group_name = str(payload.get("group_name") or payload.get("face_group_name") or "").strip()
        if not group_name:
            return "payload.group_name is required"
        if len(group_name) > 120:
            return "payload.group_name must be <= 120 characters"
        return ""

    return ""


def _is_online(terminal: GateTerminal) -> bool:
    now = timezone.now()
    source = terminal.last_heartbeat_at or terminal.last_seen_at
    if not source:
        return False
    return (now - source).total_seconds() <= 90


def _serialize_terminal(terminal: GateTerminal) -> dict:
    sync_job = DeviceSyncJob.objects.filter(device_identifier=terminal.serial_number).first()
    config = terminal.config if isinstance(terminal.config, dict) else {}
    snapshot = config.get("device_settings_snapshot", {}) if isinstance(config.get("device_settings_snapshot"), dict) else {}
    last_payload = sync_job.last_payload if sync_job and isinstance(sync_job.last_payload, dict) else {}
    device_user_total = ""
    if isinstance(last_payload.get("payload"), dict) and "total" in last_payload.get("payload", {}):
        device_user_total = last_payload["payload"].get("total", "")
    elif "total" in last_payload:
        device_user_total = last_payload.get("total", "")
    return {
        "id": str(terminal.id),
        "serial_number": terminal.serial_number,
        "display_name": terminal.display_name,
        "manufacturer": terminal.manufacturer or "",
        "model_name": terminal.model_name or "",
        "site_name": terminal.site.name if terminal.site else "",
        "direction": terminal.direction,
        "docking_mode": terminal.docking_mode,
        "approval_status": terminal.approval_status,
        "approved": terminal.is_approved,
        "ip_address": terminal.ip_address or "",
        "server_url": terminal.server_url or "",
        "server_port": terminal.server_port if terminal.server_port is not None else "",
        "firmware_version": terminal.firmware_version or "",
        "app_version": terminal.app_version or "",
        "last_seen_at": terminal.last_seen_at.isoformat() if terminal.last_seen_at else "",
        "last_heartbeat_at": terminal.last_heartbeat_at.isoformat() if terminal.last_heartbeat_at else "",
        "online": _is_online(terminal),
        "sync": {
            "last_status": sync_job.last_status if sync_job else "pending",
            "last_error": sync_job.last_error if sync_job else "",
            "last_synced_at": sync_job.last_synced_at.isoformat() if sync_job and sync_job.last_synced_at else "",
            "device_user_total": device_user_total,
        },
        "settings_snapshot": snapshot,
        "default_face_group": str(config.get("default_face_group") or ""),
        "resident_face_group": str(config.get("resident_face_group") or ""),
        "visitor_face_group": str(config.get("visitor_face_group") or ""),
    }


def _serialize_event(event: FaceDeviceEvent) -> dict:
    return {
        "id": str(event.id),
        "event_time": event.event_time.isoformat() if event.event_time else "",
        "device_identifier": event.device_identifier,
        "direction": event.direction,
        "command": event.command,
        "status": event.status,
        "remote_ip": event.remote_ip or "",
        "error": event.error or "",
        "payload": event.payload if isinstance(event.payload, dict) else {},
    }


def _serialize_action(action: FaceDeviceAction) -> dict:
    return {
        "id": str(action.id),
        "device_identifier": action.device_identifier,
        "action": action.action,
        "status": action.status,
        "requested_by": action.requested_by.username if action.requested_by else "",
        "started_at": action.started_at.isoformat() if action.started_at else "",
        "completed_at": action.completed_at.isoformat() if action.completed_at else "",
        "error": action.error or "",
        "request_payload": action.request_payload if isinstance(action.request_payload, dict) else {},
        "response_payload": action.response_payload if isinstance(action.response_payload, dict) else {},
    }


def _serialize_stranger_event(row: FaceDeviceStrangerEvent, request=None) -> dict:
    snapshot_url = row.snapshot_image.url if row.snapshot_image else ""
    panoramic_url = row.panoramic_image.url if row.panoramic_image else ""
    if request:
        if snapshot_url:
            snapshot_url = request.build_absolute_uri(snapshot_url)
        if panoramic_url:
            panoramic_url = request.build_absolute_uri(panoramic_url)
    return {
        "id": str(row.id),
        "event_time": row.event_time.isoformat() if row.event_time else "",
        "device_identifier": row.device_identifier,
        "source_command": row.source_command,
        "status": row.status,
        "confidence": str(row.confidence) if row.confidence is not None else "",
        "liveness_score": str(row.liveness_score) if row.liveness_score is not None else "",
        "credential_type": row.credential_type or "",
        "credential_value": row.credential_value or "",
        "face_group_name": row.face_group_name or "",
        "remote_ip": row.remote_ip or "",
        "terminal_id": str(row.terminal_id) if row.terminal_id else "",
        "terminal_name": row.terminal.display_name if row.terminal else "",
        "access_log_id": str(row.access_log_id) if row.access_log_id else "",
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else "",
        "reviewed_by": row.reviewed_by.username if row.reviewed_by else "",
        "review_notes": row.review_notes or "",
        "promoted_person_id": str(row.promoted_person_id) if row.promoted_person_id else "",
        "snapshot_image_url": snapshot_url,
        "panoramic_image_url": panoramic_url,
        "payload": sanitize_face_payload(row.payload if isinstance(row.payload, dict) else {}),
    }


def _build_access_log_photo_report(row: FaceDeviceAccessLog, *, person_name: str, user_name: str, user_id: str, confidence_text: str, decision_label: str, access_granted: bool) -> dict:
    snapshot_meta = {}
    if row.snapshot_image:
        try:
            snapshot_meta = describe_uploaded_photo(row.snapshot_image)
        except Exception:
            snapshot_meta = {}

    size_bytes = int(snapshot_meta.get("size_bytes") or getattr(row.snapshot_image, "size", 0) or 0)
    width = int(snapshot_meta.get("width") or 0)
    height = int(snapshot_meta.get("height") or 0)
    format_name = str(snapshot_meta.get("format") or "").upper()
    dpi_x = int(snapshot_meta.get("dpi_x") or 0)
    dpi_y = int(snapshot_meta.get("dpi_y") or 0)
    logged_at = row.event_time.strftime("%Y-%m-%d %H:%M:%S") if row.event_time else ""
    file_size_text = f"{max(1, int(round(size_bytes / 1024)))}KB" if size_bytes else ""
    resolution_text = f"{dpi_x}(PPI)x{dpi_y}(PPI)" if dpi_x and dpi_y else ""
    dimensions_text = f"{width}(w) * {height}(h)" if width and height else ""
    display_name = person_name or user_name or "Visitor"
    contact_text = person_name or user_name or user_id or ""
    photo_text = " - ".join(part for part in [display_name, user_id] if part)
    labels = []
    if row.snapshot_image:
        labels.extend(
            [
                {"label": "Face", "confidence": 99.88},
                {"label": "Head", "confidence": 99.88},
                {"label": "Person", "confidence": 99.88},
                {"label": "Portrait", "confidence": 99.88},
            ]
        )
    if access_granted:
        labels.append({"label": "Granted", "confidence": 100.0})
    elif decision_label == "Denied":
        labels.append({"label": "Denied", "confidence": 100.0})

    return {
        "photo_type": "Contact",
        "Photo Type": "Contact",
        "contact": contact_text,
        "Contact": contact_text,
        "creation_date": logged_at,
        "Creation Date": logged_at,
        "date_logged": logged_at,
        "Date Logged": logged_at,
        "photo_text": photo_text,
        "Photo Text": photo_text,
        "user": person_name or user_name or "Admin",
        "User": person_name or user_name or "Admin",
        "file_size": file_size_text,
        "File Size": file_size_text,
        "file_format": format_name,
        "File Format": format_name,
        "resolution": resolution_text,
        "Resolution": resolution_text,
        "dimensions": dimensions_text,
        "Dimensions": dimensions_text,
        "confidence": confidence_text,
        "Confidence": confidence_text,
        "object_detection_labels": labels,
        "Object Detection Labels": labels,
    }


def _serialize_access_log(row: FaceDeviceAccessLog, request=None) -> dict:
    snapshot_url = row.snapshot_image.url if row.snapshot_image else ""
    panoramic_url = row.panoramic_image.url if row.panoramic_image else ""
    if request:
        if snapshot_url:
            snapshot_url = request.build_absolute_uri(snapshot_url)
        if panoramic_url:
            panoramic_url = request.build_absolute_uri(panoramic_url)
    resolved_person = row.person
    payload = sanitize_face_payload(row.payload)
    user_id = ""
    user_name = ""
    recog_type = ""
    pass_status = ""
    search_score = ""
    liveness_score = ""
    face_token = ""
    event_card_number = ""
    face_group_name = ""
    credential_type = ""
    credential_value = ""
    if isinstance(payload, dict):
        user_id = _payload_value(payload, ["user_id", "user id", "userid", "uid", "person_id"])
        user_name = _payload_value(payload, ["user_name", "name", "Name", "person_name"])
        recog_type = _payload_value(payload, ["recog_type", "type"])
        pass_status = _payload_value(payload, ["pass_status", "pass status"])
        search_score = _payload_value(payload, ["search_score", "score", "similarity", "match_score", "face_score"])
        liveness_score = _payload_value(payload, ["liveness_score", "liveness", "live_score", "livenessscore"])
        face_token = _payload_value(payload, ["face_token", "facetoken", "token"])
        event_card_number = _payload_value(payload, ["card_number", "Ic", "ic", "id_card", "id_number"])
        face_group_name = _payload_value(payload, ["face_group_name", "group_name", "group"])
        credential_value = _payload_value(payload, ["qr_code", "qrcode", "qr", "barcode", "scan_data"])
        if credential_value:
            credential_type = "qr"
        elif event_card_number:
            credential_type = "card"
            credential_value = event_card_number

    # Fallback: map device-reported user_id to synced Django Person when direct FK is missing.
    if resolved_person is None and user_id:
        state_row = (
            FaceDeviceUserState.objects.select_related("person")
            .filter(device_identifier=row.device_identifier, user_identifier=user_id, person__isnull=False)
            .first()
        )
        if state_row and state_row.person:
            resolved_person = state_row.person

    if resolved_person is None and user_id:
        person_fallback = Person.objects.filter(face_subject_id=user_id).first()
        if person_fallback:
            resolved_person = person_fallback
    if resolved_person is None and user_id:
        person_fallback = Person.objects.filter(id_number=user_id).first()
        if person_fallback:
            resolved_person = person_fallback
    if resolved_person is None and user_id:
        person_fallback = Person.objects.filter(phone=user_id).first()
        if person_fallback:
            resolved_person = person_fallback
    if resolved_person is None and user_id:
        person_fallback = Person.objects.filter(card_number=user_id).first()
        if person_fallback:
            resolved_person = person_fallback
    if resolved_person is None and user_name and user_name.strip().lower() not in {"visitor", "unknown", "stranger"}:
        name_text = user_name.strip()
        # Exact first/last-name fallback only when unique, to avoid accidental mis-assignment.
        name_parts = [part for part in name_text.split() if part]
        if len(name_parts) >= 2:
            full_name_matches = list(
                Person.objects.filter(
                    first_name__iexact=name_parts[0],
                    last_name__iexact=" ".join(name_parts[1:]),
                )[:2]
            )
            if len(full_name_matches) == 1:
                resolved_person = full_name_matches[0]

    pass_tokens = {"1", "true", "pass", "allow", "granted", "open"}
    deny_tokens = {"0", "false", "deny", "denied", "block", "blocked", "reject", "rejected", "close", "closed"}
    pass_status_text = str(pass_status or "").strip().lower()
    user_name_lc = str(user_name or "").strip().lower()
    is_stranger_event = row.result == "unknown" and (
        user_name_lc in {"visitor", "unknown", "stranger"} or not bool(resolved_person)
    )
    if is_stranger_event:
        decision_label = "Stranger"
        access_granted = False
    elif row.result == "pass" or pass_status_text in pass_tokens:
        decision_label = "Granted"
        access_granted = True
    elif row.result == "deny" or pass_status_text in deny_tokens:
        decision_label = "Denied"
        access_granted = False
    elif pass_status_text != "":
        decision_label = "Denied"
        access_granted = False
    else:
        decision_label = "Unknown"
        access_granted = False

    visitor_like_names = {"", "visitor", "unknown", "stranger"}
    has_confident_match = (row.confidence is not None and row.confidence > 0)
    recognition_matched = bool(resolved_person) or bool(
        user_id and user_name_lc not in visitor_like_names and has_confident_match
    )
    recognition_label = "Matched" if recognition_matched else "Unknown"

    person_name = resolved_person.full_name if resolved_person else ""
    terminal = row.terminal
    where_site = terminal.site.name if terminal and terminal.site else ""
    where_access_point = terminal.access_point.name if terminal and terminal.access_point else ""
    where_direction = terminal.direction if terminal else ""
    device_name = terminal.display_name if terminal else ""
    analysis_report = _build_access_log_photo_report(
        row,
        person_name=person_name,
        user_name=user_name,
        user_id=user_id,
        confidence_text=str(row.confidence) if row.confidence is not None else "",
        decision_label=decision_label,
        access_granted=access_granted,
    )
    return {
        "id": str(row.id),
        "event_time": row.event_time.isoformat() if row.event_time else "",
        "device_identifier": row.device_identifier,
        "device_name": device_name,
        "site_name": where_site,
        "access_point_name": where_access_point,
        "direction": where_direction,
        "source_command": row.source_command,
        "result": row.result,
        "decision_label": decision_label,
        "access_granted": access_granted,
        "recognition_label": recognition_label,
        "recognition_matched": recognition_matched,
        "confidence": str(row.confidence) if row.confidence is not None else "",
        "person_id": str(resolved_person.id) if resolved_person else "",
        "person_name": person_name,
        "person_id_number": resolved_person.id_number if resolved_person else "",
        "person_phone": resolved_person.phone if resolved_person else "",
        "matched_person": bool(resolved_person),
        "event_user_id": user_id,
        "event_user_name": user_name,
        "event_recog_type": recog_type,
        "event_pass_status": pass_status,
        "event_search_score": search_score,
        "event_liveness_score": liveness_score,
        "event_face_token": face_token,
        "event_card_number": event_card_number,
        "event_face_group_name": face_group_name,
        "credential_type": credential_type,
        "credential_value": credential_value,
        "is_stranger_event": is_stranger_event,
        "snapshot_image_url": snapshot_url,
        "panoramic_image_url": panoramic_url,
        "remote_ip": row.remote_ip or "",
        "payload": payload,
        "photo_analysis_report": analysis_report,
    }


def _serialize_user_state(row: FaceDeviceUserState) -> dict:
    return {
        "id": str(row.id),
        "device_identifier": row.device_identifier,
        "user_identifier": row.user_identifier,
        "state": row.state,
        "person_id": str(row.person_id) if row.person_id else "",
        "person_name": row.person.full_name if row.person else "",
        "last_seen_on_device_at": row.last_seen_on_device_at.isoformat() if row.last_seen_on_device_at else "",
        "payload": row.payload if isinstance(row.payload, dict) else {},
    }


def _sync_summary_for_terminal(terminal: GateTerminal) -> dict:
    queryset = FaceDeviceUserState.objects.filter(device_identifier=terminal.serial_number).select_related("person")
    total = queryset.count()
    missing_rows = list(queryset.filter(state="missing").order_by("user_identifier")[:100])
    unexpected_rows = list(queryset.filter(state="unexpected").order_by("user_identifier")[:100])
    present_count = queryset.filter(state="present").count()
    pending_actions = FaceDeviceAction.objects.filter(
        device_identifier=terminal.serial_number,
        status__in=["pending", "running"],
    ).count()
    return {
        "counts": {
            "tracked_total": total,
            "present": present_count,
            "missing": len(missing_rows),
            "unexpected": len(unexpected_rows),
            "pending_actions": pending_actions,
        },
        "missing_users": [_serialize_user_state(item) for item in missing_rows],
        "unexpected_users": [_serialize_user_state(item) for item in unexpected_rows],
    }


def _parse_datetime_value(raw: str):
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    parsed = parse_datetime(text.replace(" ", "T"))
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _filter_access_logs_queryset(request, *, terminal_id=None):
    queryset = FaceDeviceAccessLog.objects.select_related("person", "terminal", "terminal__site", "terminal__access_point").order_by("-event_time")
    if terminal_id:
        terminal = get_object_or_404(GateTerminal, id=terminal_id)
        queryset = queryset.filter(device_identifier=terminal.serial_number)
    else:
        serial = (request.query_params.get("serial_number") or "").strip()
        if serial:
            queryset = queryset.filter(device_identifier=serial)

    result_value = (request.query_params.get("result") or "").strip()
    if result_value:
        queryset = queryset.filter(result=result_value)
    person_query = (request.query_params.get("person") or "").strip()
    if person_query:
        queryset = queryset.filter(
            Q(person__first_name__icontains=person_query)
            | Q(person__last_name__icontains=person_query)
            | Q(person__id_number__icontains=person_query)
            | Q(person__phone__icontains=person_query)
            | Q(payload__user_name__icontains=person_query)
            | Q(payload__name__icontains=person_query)
            | Q(payload__person_name__icontains=person_query)
            | Q(payload__user_id__icontains=person_query)
            | Q(payload__userid__icontains=person_query)
            | Q(payload__uid__icontains=person_query)
            | Q(payload__id_number__icontains=person_query)
            | Q(payload__id_card__icontains=person_query)
            | Q(payload__phone__icontains=person_query)
            | Q(payload__mobile__icontains=person_query)
        )
    command = (request.query_params.get("command") or "").strip()
    if command:
        queryset = queryset.filter(source_command=command)
    start_at = _parse_datetime_value(request.query_params.get("start_at") or request.query_params.get("date_from") or "")
    end_at = _parse_datetime_value(request.query_params.get("end_at") or request.query_params.get("date_to") or "")
    if start_at:
        queryset = queryset.filter(event_time__gte=start_at)
    if end_at:
        queryset = queryset.filter(event_time__lte=end_at)
    return queryset


def _read_pagination(request, *, default_size: int = 100, max_size: int = 300) -> tuple[int, int]:
    limit = request.query_params.get("limit")
    page_size_raw = request.query_params.get("page_size", limit)
    page_raw = request.query_params.get("page", "1")
    try:
        page_size = int(page_size_raw)
    except Exception:
        page_size = default_size
    try:
        page = int(page_raw)
    except Exception:
        page = 1
    page_size = max(1, min(max_size, page_size))
    page = max(1, page)
    return page, page_size


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_app_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden
    return Response(
        {
            "app": "face_devices",
            "status": "phase_a",
            "message": "Face device management app is active.",
            "planned_modules": [
                "inventory",
                "status",
                "settings",
                "actions",
                "sync",
                "access_logs",
                "audit",
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_list(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    queryset = GateTerminal.objects.select_related("site").all().order_by("display_name", "serial_number")
    site = (request.query_params.get("site") or "").strip()
    approval = (request.query_params.get("approval_status") or "").strip()
    if site:
        queryset = queryset.filter(site__name__iexact=site)
    if approval:
        queryset = queryset.filter(approval_status=approval)
    terminals = list(queryset)
    response_rows = [_serialize_terminal(item) for item in terminals]

    online_only = request.query_params.get("online")
    if online_only in {"true", "1"}:
        response_rows = [item for item in response_rows if item["online"]]
    elif online_only in {"false", "0"}:
        response_rows = [item for item in response_rows if not item["online"]]

    return Response(
        {
            "count": len(response_rows),
            "items": response_rows,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_detail(request, terminal_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    terminal = get_object_or_404(GateTerminal.objects.select_related("site", "access_point"), id=terminal_id)
    payload = _serialize_terminal(terminal)
    payload["access_point_name"] = terminal.access_point.name if terminal.access_point else ""
    payload["notes"] = terminal.notes or ""
    payload["recent_events"] = [
        _serialize_event(item)
        for item in FaceDeviceEvent.objects.filter(device_identifier=terminal.serial_number).order_by("-event_time")[:10]
    ]
    payload["recent_actions"] = [
        _serialize_action(item)
        for item in FaceDeviceAction.objects.filter(device_identifier=terminal.serial_number).order_by("-created_at")[:10]
    ]
    payload["recent_access_logs"] = [
        _serialize_access_log(item, request=request)
        for item in FaceDeviceAccessLog.objects.filter(device_identifier=terminal.serial_number).select_related("person", "terminal", "terminal__site", "terminal__access_point").order_by("-event_time")[:10]
    ]
    payload["recent_stranger_events"] = [
        _serialize_stranger_event(item, request=request)
        for item in FaceDeviceStrangerEvent.objects.filter(device_identifier=terminal.serial_number).select_related("terminal", "reviewed_by").order_by("-event_time")[:10]
    ]
    payload["sync_state"] = _sync_summary_for_terminal(terminal)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_events(request, terminal_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    terminal = get_object_or_404(GateTerminal, id=terminal_id)
    queryset = FaceDeviceEvent.objects.filter(device_identifier=terminal.serial_number).order_by("-event_time")
    command = (request.query_params.get("command") or "").strip()
    if command:
        queryset = queryset.filter(command=command)
    direction = (request.query_params.get("direction") or "").strip()
    if direction:
        queryset = queryset.filter(direction=direction)
    start_at = _parse_datetime_value(request.query_params.get("start_at") or request.query_params.get("date_from") or "")
    end_at = _parse_datetime_value(request.query_params.get("end_at") or request.query_params.get("date_to") or "")
    if start_at:
        queryset = queryset.filter(event_time__gte=start_at)
    if end_at:
        queryset = queryset.filter(event_time__lte=end_at)

    page, page_size = _read_pagination(request, default_size=100, max_size=300)
    paginator = Paginator(queryset, page_size)
    try:
        chunk = paginator.page(page)
    except EmptyPage:
        chunk = paginator.page(paginator.num_pages if paginator.num_pages else 1)
    rows = [_serialize_event(item) for item in chunk.object_list]
    return Response(
        {
            "count": len(rows),
            "total_count": paginator.count,
            "page": chunk.number,
            "total_pages": paginator.num_pages,
            "page_size": page_size,
            "items": rows,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def face_device_actions(request, terminal_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    terminal = get_object_or_404(GateTerminal, id=terminal_id)
    if request.method == "POST":
        action = str(request.data.get("action") or "").strip()
        if not action:
            return Response({"detail": "action is required"}, status=status.HTTP_400_BAD_REQUEST)
        allowed = {value for value, _ in FaceDeviceAction.ACTION_CHOICES}
        if action not in allowed:
            return Response({"detail": f"Unsupported action: {action}"}, status=status.HTTP_400_BAD_REQUEST)
        if action in DESTRUCTIVE_ACTIONS and not _can_run_destructive_action(request):
            return Response(
                {
                    "detail": "Forbidden: destructive actions require superuser or "
                    "`face_devices.can_run_destructive_face_device_actions` permission."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        payload = request.data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        validation_error = _validate_action_payload(action, payload)
        if validation_error:
            return Response({"detail": validation_error}, status=status.HTTP_400_BAD_REQUEST)
        row = queue_face_device_action(
            terminal=terminal,
            action=action,
            request_payload=payload,
            requested_by=request.user,
        )
        return Response({"success": True, "action": _serialize_action(row)}, status=status.HTTP_201_CREATED)

    queryset = FaceDeviceAction.objects.select_related("requested_by").filter(device_identifier=terminal.serial_number).order_by("-created_at")
    action = (request.query_params.get("action") or "").strip()
    if action:
        queryset = queryset.filter(action=action)
    status_value = (request.query_params.get("status") or "").strip()
    if status_value:
        queryset = queryset.filter(status=status_value)
    limit = request.query_params.get("limit")
    try:
        max_items = max(1, min(200, int(limit))) if limit is not None else 100
    except Exception:
        max_items = 100

    rows = [_serialize_action(item) for item in queryset[:max_items]]
    return Response({"count": len(rows), "items": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_access_logs(request, terminal_id=None):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    queryset = _filter_access_logs_queryset(request, terminal_id=terminal_id)

    page, page_size = _read_pagination(request, default_size=100, max_size=300)
    paginator = Paginator(queryset, page_size)
    try:
        chunk = paginator.page(page)
    except EmptyPage:
        chunk = paginator.page(paginator.num_pages if paginator.num_pages else 1)
    rows = [_serialize_access_log(item, request=request) for item in chunk.object_list]
    return Response(
        {
            "count": len(rows),
            "total_count": paginator.count,
            "page": chunk.number,
            "total_pages": paginator.num_pages,
            "page_size": page_size,
            "items": rows,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_access_logs_export_csv(request, terminal_id=None):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    queryset = _filter_access_logs_queryset(request, terminal_id=terminal_id)
    filename = "face_access_logs.csv" if not terminal_id else f"face_access_logs_{terminal_id}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    headers = [
        "id",
        "event_time",
        "device_identifier",
        "device_name",
        "site_name",
        "access_point_name",
        "direction",
        "source_command",
        "result",
        "decision_label",
        "access_granted",
        "matched_person",
        "confidence",
        "person_id",
        "person_name",
        "person_id_number",
        "person_phone",
        "event_user_id",
        "event_user_name",
        "event_recog_type",
        "event_pass_status",
        "event_search_score",
        "event_liveness_score",
        "event_face_token",
        "event_card_number",
        "event_face_group_name",
        "credential_type",
        "credential_value",
        "is_stranger_event",
        "photo_type",
        "photo_text",
        "file_size",
        "file_format",
        "resolution",
        "dimensions",
        "remote_ip",
        "snapshot_image_url",
        "panoramic_image_url",
        "object_detection_labels",
        "payload_json",
    ]
    writer.writerow(headers)

    for row in queryset.iterator():
        item = _serialize_access_log(row, request=request)
        writer.writerow(
            [
                item.get("id", ""),
                item.get("event_time", ""),
                item.get("device_identifier", ""),
                item.get("device_name", ""),
                item.get("site_name", ""),
                item.get("access_point_name", ""),
                item.get("direction", ""),
                item.get("source_command", ""),
                item.get("result", ""),
                item.get("decision_label", ""),
                "yes" if item.get("access_granted") else "no",
                "yes" if item.get("matched_person") else "no",
                item.get("confidence", ""),
                item.get("person_id", ""),
                item.get("person_name", ""),
                item.get("person_id_number", ""),
                item.get("person_phone", ""),
                item.get("event_user_id", ""),
                item.get("event_user_name", ""),
                item.get("event_recog_type", ""),
                item.get("event_pass_status", ""),
                item.get("event_search_score", ""),
                item.get("event_liveness_score", ""),
                item.get("event_face_token", ""),
                item.get("event_card_number", ""),
                item.get("event_face_group_name", ""),
                item.get("credential_type", ""),
                item.get("credential_value", ""),
                "yes" if item.get("is_stranger_event") else "no",
                item.get("photo_analysis_report", {}).get("Photo Type", item.get("photo_analysis_report", {}).get("photo_type", "")),
                item.get("photo_analysis_report", {}).get("Photo Text", item.get("photo_analysis_report", {}).get("photo_text", "")),
                item.get("photo_analysis_report", {}).get("File Size", item.get("photo_analysis_report", {}).get("file_size", "")),
                item.get("photo_analysis_report", {}).get("File Format", item.get("photo_analysis_report", {}).get("file_format", "")),
                item.get("photo_analysis_report", {}).get("Resolution", item.get("photo_analysis_report", {}).get("resolution", "")),
                item.get("photo_analysis_report", {}).get("Dimensions", item.get("photo_analysis_report", {}).get("dimensions", "")),
                item.get("remote_ip", ""),
                item.get("snapshot_image_url", ""),
                item.get("panoramic_image_url", ""),
                json.dumps(item.get("photo_analysis_report", {}).get("Object Detection Labels", item.get("photo_analysis_report", {}).get("object_detection_labels", [])), ensure_ascii=True, separators=(",", ":")),
                json.dumps(item.get("payload", {}), ensure_ascii=True, separators=(",", ":")),
            ]
        )

    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def face_device_access_logs_import_csv(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "file is required (CSV/XLS/XLSX)."}, status=status.HTTP_400_BAD_REQUEST)

    serial_number = str(request.data.get("serial_number") or request.query_params.get("serial_number") or "").strip()
    if not serial_number:
        return Response({"detail": "serial_number is required."}, status=status.HTTP_400_BAD_REQUEST)

    terminal = GateTerminal.objects.filter(serial_number=serial_number).first()
    raw_bytes = upload.read()
    if not raw_bytes:
        return Response({"detail": "Uploaded file is empty."}, status=status.HTTP_400_BAD_REQUEST)

    parsed_rows_data, headers, parse_error = _read_tabular_upload(upload.name, raw_bytes)
    if parse_error:
        return Response({"detail": parse_error}, status=status.HTTP_400_BAD_REQUEST)
    if not headers:
        return Response({"detail": "Uploaded file has no headers."}, status=status.HTTP_400_BAD_REQUEST)

    records: list[dict] = []
    parsed_rows = 0
    for row in parsed_rows_data:
        parsed_rows += 1
        user_id = _csv_row_value(row, ["user_id", "user id", "userid", "uid", "IC", "ic"])
        user_name = _csv_row_value(row, ["Name", "name", "user_name", "person_name"])
        recog_time = _csv_row_value(row, ["Recognition time", "recognition_time", "recog_time", "event_time", "time"])
        confidence = _csv_row_value(row, ["Confidence", "confidence", "score", "similarity"])
        id_card = _csv_row_value(row, ["ID card number", "id_card", "id_number"])
        phone = _csv_row_value(row, ["Cellphone number", "cellphone_number", "phone", "mobile"])
        image_value = _csv_row_value(row, ["image", "photo", "snapshot"])
        pass_status_raw = _csv_row_value(row, ["pass_status", "pass status", "passstatus", "granted"])
        result_raw = _csv_row_value(row, ["result", "decision", "status", "access_result"])

        if not any([user_id, user_name, recog_time, confidence, id_card, phone, image_value]):
            continue

        pass_status, result = _import_decision(
            pass_status_raw=pass_status_raw,
            result_raw=result_raw,
            user_name=user_name,
            confidence_raw=confidence,
        )
        record = {
            "user_id": user_id,
            "user_name": user_name,
            "name": user_name,
            "recog_time": recog_time,
            "confidence": confidence,
            "id_card": id_card,
            "id_number": id_card,
            "phone": phone,
            "image": image_value,
            "pass_status": pass_status,
            "result": result,
            "source": "csv_import",
        }
        records.append(record)

    if not records:
        return Response(
            {"detail": "No usable rows found in CSV.", "parsed_rows": parsed_rows, "created": 0},
            status=status.HTTP_400_BAD_REQUEST,
        )

    created_rows = ingest_face_device_access_log(
        terminal=terminal,
        device_identifier=serial_number,
        command="getRecordRet",
        payload={"records": records},
        remote_ip=None,
    )
    return Response(
        {
            "success": True,
            "serial_number": serial_number,
            "parsed_rows": parsed_rows,
            "ingested_records": len(records),
            "created": len(created_rows),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_sync_status(request, terminal_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    terminal = get_object_or_404(GateTerminal, id=terminal_id)
    sync_job = DeviceSyncJob.objects.filter(device_identifier=terminal.serial_number).first()
    summary = _sync_summary_for_terminal(terminal)
    return Response(
        {
            "device_identifier": terminal.serial_number,
            "device_name": terminal.display_name,
            "last_sync_status": sync_job.last_status if sync_job else "pending",
            "last_sync_error": sync_job.last_error if sync_job else "",
            "last_synced_at": sync_job.last_synced_at.isoformat() if sync_job and sync_job.last_synced_at else "",
            **summary,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def face_device_stranger_events(request, terminal_id=None):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    queryset = FaceDeviceStrangerEvent.objects.select_related("terminal", "reviewed_by", "promoted_person").order_by("-event_time")
    if terminal_id:
        terminal = get_object_or_404(GateTerminal, id=terminal_id)
        queryset = queryset.filter(device_identifier=terminal.serial_number)
    else:
        serial = (request.query_params.get("serial_number") or "").strip()
        if serial:
            queryset = queryset.filter(device_identifier=serial)

    status_value = (request.query_params.get("status") or "").strip()
    if status_value:
        queryset = queryset.filter(status=status_value)
    credential_type = (request.query_params.get("credential_type") or "").strip()
    if credential_type:
        queryset = queryset.filter(credential_type=credential_type)

    page, page_size = _read_pagination(request, default_size=100, max_size=300)
    paginator = Paginator(queryset, page_size)
    try:
        chunk = paginator.page(page)
    except EmptyPage:
        chunk = paginator.page(paginator.num_pages if paginator.num_pages else 1)
    rows = [_serialize_stranger_event(item, request=request) for item in chunk.object_list]
    return Response(
        {
            "count": len(rows),
            "total_count": paginator.count,
            "page": chunk.number,
            "total_pages": paginator.num_pages,
            "page_size": page_size,
            "items": rows,
        }
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def face_device_stranger_event_detail(request, stranger_event_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    row = get_object_or_404(FaceDeviceStrangerEvent, id=stranger_event_id)
    next_status = str(request.data.get("status") or "").strip()
    if next_status not in {"new", "reviewed", "dismissed", "promoted"}:
        return Response({"detail": "status must be one of: new, reviewed, dismissed, promoted"}, status=status.HTTP_400_BAD_REQUEST)

    row.status = next_status
    row.review_notes = str(request.data.get("review_notes") or row.review_notes or "").strip()
    row.reviewed_at = timezone.now()
    row.reviewed_by = request.user

    person_id = str(request.data.get("promoted_person_id") or "").strip()
    if next_status == "promoted":
        if not person_id:
            return Response({"detail": "promoted_person_id is required when status=promoted"}, status=status.HTTP_400_BAD_REQUEST)
        promoted_person = Person.objects.filter(id=person_id).first()
        if not promoted_person:
            return Response({"detail": "promoted_person_id not found"}, status=status.HTTP_400_BAD_REQUEST)
        row.promoted_person = promoted_person
    else:
        row.promoted_person = None

    row.save(update_fields=["status", "review_notes", "reviewed_at", "reviewed_by", "promoted_person", "modified_at"])
    return Response({"success": True, "stranger_event": _serialize_stranger_event(row, request=request)})
