import base64
import io
import mimetypes

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.conf import settings
from GateCore.models import AuditTrail, Blacklist, DeviceSyncJob, GateTerminal, Person, Unit, VisitorFaceAccessGrant
from GateCore.services.mobile_auth import build_photo_display_url
from face_devices.services import queue_face_device_action


def _terminal_face_group_value(terminal: GateTerminal | None, key: str, default: str = "") -> str:
    if terminal is None or not isinstance(terminal.config, dict):
        return default
    value = terminal.config.get(key)
    if value not in (None, ""):
        return str(value).strip()
    snapshot = terminal.config.get("device_settings_snapshot")
    if isinstance(snapshot, dict):
        value = snapshot.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _resolve_face_group_name(
    *,
    person: Person,
    terminal: GateTerminal | None = None,
    is_visitor: bool = False,
    has_active_occupancy: bool | None = None,
) -> str:
    if is_visitor:
        return (
            _terminal_face_group_value(terminal, "visitor_face_group")
            or _terminal_face_group_value(terminal, "default_face_group")
            or "visitors"
        )

    if has_active_occupancy is None:
        has_active_occupancy = person.occupancies.filter(is_active=True, is_deleted=False).exists()
    if has_active_occupancy:
        return (
            _terminal_face_group_value(terminal, "resident_face_group")
            or _terminal_face_group_value(terminal, "default_face_group")
            or "residents"
        )

    return _terminal_face_group_value(terminal, "default_face_group")


def _require_device_or_staff(request):
    token = (request.headers.get("X-Device-Sync-Token") or request.META.get("HTTP_X_DEVICE_SYNC_TOKEN") or "").strip()
    expected = (getattr(settings, "GATE_DEVICE_SYNC_TOKEN", "") or "").strip()
    if expected and token and token == expected:
        return None
    if request.user.is_authenticated and request.user.is_staff:
        return None
    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


def _parse_cursor(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    return parse_datetime(str(value))


def _short_date(value):
    return value.isoformat() if value else ""


def _format_device_datetime(value) -> str:
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


def _build_inline_photo_data_uri(photo_field, *, max_width: int = 640, max_height: int = 640) -> str:
    if not photo_field:
        return ""

    try:
        photo_field.open("rb")
        photo_bytes = photo_field.read()
        if not photo_bytes:
            return ""

        try:
            from PIL import Image, ImageOps

            img = Image.open(io.BytesIO(photo_bytes))
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB",):
                img = img.convert("RGB")
            w, h = img.size
            if w > max_width or h > max_height:
                img.thumbnail((max_width, max_height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90, optimize=True)
            photo_bytes = buf.getvalue()
        except Exception:
            pass

        encoded = base64.b64encode(photo_bytes).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return ""
    finally:
        try:
            photo_field.close()
        except Exception:
            pass


def build_face_device_add_user_payload(
    person: Person,
    *,
    terminal: GateTerminal | None = None,
    effect_time=None,
    end_time=None,
    max_pass_count=None,
    pass_count_cycle=None,
    user_type=None,
    pass_rule_id: str | None = None,
    is_visitor: bool = False,
) -> dict:
    photo_url = _build_inline_photo_data_uri(getattr(person, "photo", None))
    # TMT devices expect raw base64 without the data URI prefix.
    face_template = photo_url
    if face_template.startswith("data:") and ";base64," in face_template:
        face_template = face_template.split(",", 1)[1]
    user_id = (getattr(person, "face_subject_id", "") or str(person.id)).strip()
    full_name = (getattr(person, "full_name", "") or "").strip()
    id_number = (getattr(person, "id_number", "") or getattr(person, "phone", "") or user_id).strip()

    payload = {
        "user_id": user_id,
        "id_name": full_name,
        "name": full_name,
        "id_number": id_number,
        "id_card": id_number,
        "phone": (getattr(person, "phone", "") or "").strip(),
        "face_template": face_template,
        "tts_name": (getattr(person, "face_tts_name", "") or full_name).strip(),
    }

    face_group_name = _resolve_face_group_name(person=person, terminal=terminal, is_visitor=is_visitor)
    if face_group_name:
        payload["face_group_name"] = face_group_name

    card_number = (getattr(person, "card_number", "") or "").strip()
    if card_number:
        payload["Ic"] = card_number

    resolved_user_type = user_type if user_type not in (None, "") else getattr(person, "face_user_type", None)
    if resolved_user_type not in (None, ""):
        try:
            payload["user_type"] = int(resolved_user_type)
        except Exception:
            pass

    resolved_effect_time = effect_time
    if resolved_effect_time:
        payload["effect_time"] = _format_device_datetime(resolved_effect_time)

    resolved_end_time = end_time
    if resolved_end_time:
        rendered_end_time = _format_device_datetime(resolved_end_time)
        payload["end_time"] = rendered_end_time
        payload["valid_until"] = rendered_end_time

    access_password = (getattr(person, "face_access_password", "") or "").strip()
    if access_password:
        payload["password"] = access_password

    resolved_pass_rule_id = (pass_rule_id if pass_rule_id is not None else getattr(person, "face_pass_rule_id", "")) or ""
    resolved_pass_rule_id = str(resolved_pass_rule_id).strip()
    if resolved_pass_rule_id:
        payload["pass_rule_id"] = resolved_pass_rule_id

    resolved_max_pass_count = max_pass_count if max_pass_count not in (None, "") else getattr(person, "face_max_pass_count", None)
    if resolved_max_pass_count not in (None, ""):
        try:
            payload["max_pass_count"] = int(resolved_max_pass_count)
        except Exception:
            pass

    resolved_pass_count_cycle = pass_count_cycle if pass_count_cycle not in (None, "") else getattr(person, "face_pass_count_cycle", None)
    if resolved_pass_count_cycle not in (None, ""):
        try:
            payload["pass_count_cycle"] = int(resolved_pass_count_cycle)
        except Exception:
            pass

    return payload


def queue_face_device_person_sync(person: Person, *, requested_by=None) -> int:
    if not person or not getattr(person, "facial_recognition_enabled", False):
        return 0
    if getattr(person, "face_enrollment_status", "") not in {"approved", "synced"}:
        return 0
    if not getattr(person, "photo", None):
        return 0

    terminals = GateTerminal.objects.filter(approval_status="approved")
    site_ids = list(
        person.occupancies.filter(is_active=True, is_deleted=False)
        .values_list("unit__property__site_id", flat=True)
    )
    site_ids = [site_id for site_id in site_ids if site_id]
    if site_ids:
        site_terminals = terminals.filter(site_id__in=site_ids)
        terminals = site_terminals if site_terminals.exists() else terminals

    queued = 0
    for terminal in terminals:
        payload = build_face_device_add_user_payload(person, terminal=terminal)
        queue_face_device_action(
            terminal=terminal,
            action="add_user",
            request_payload=payload,
            requested_by=requested_by,
        )
        queued += 1
    return queued


def queue_face_device_delete_user(terminal: GateTerminal, person: Person, *, requested_by=None) -> bool:
    user_id = (getattr(person, "face_subject_id", "") or str(person.id)).strip()
    if not terminal or not user_id:
        return False
    queue_face_device_action(
        terminal=terminal,
        action="delete_user",
        request_payload={"user_id": user_id},
        requested_by=requested_by,
    )
    return True


def build_visitor_face_device_add_user_payload(grant: VisitorFaceAccessGrant) -> dict:
    person = grant.person
    return build_face_device_add_user_payload(
        person,
        terminal=grant.entry_terminal or grant.exit_terminal,
        effect_time=grant.valid_from,
        end_time=grant.valid_until,
        max_pass_count=1,
        pass_count_cycle=0,
        is_visitor=True,
    )


def queue_visitor_face_grant_sync(grant: VisitorFaceAccessGrant, *, requested_by=None) -> dict[str, int]:
    if not grant or not grant.person_id:
        return {"entry": 0, "exit": 0, "total": 0}

    person = grant.person
    if not person.facial_recognition_enabled:
        return {"entry": 0, "exit": 0, "total": 0}
    if getattr(person, "face_enrollment_status", "") not in {"approved", "synced"}:
        return {"entry": 0, "exit": 0, "total": 0}
    if not getattr(person, "photo", None):
        return {"entry": 0, "exit": 0, "total": 0}

    queued = {"entry": 0, "exit": 0, "total": 0}
    terminals = [
        ("entry", grant.entry_terminal),
        ("exit", grant.exit_terminal),
    ]
    if not any(terminal and terminal.approval_status == "approved" for _, terminal in terminals):
        fallback_terminals = GateTerminal.objects.filter(approval_status="approved")
        guest_registration = getattr(grant, "guest_registration", None)
        unit = getattr(guest_registration, "unit", None) if guest_registration else None
        property_obj = getattr(unit, "property", None) if unit else None
        site = getattr(property_obj, "site", None) if property_obj else None
        if site:
            site_terminals = fallback_terminals.filter(site=site)
            terminals = [("site", terminal) for terminal in site_terminals] or [("all", terminal) for terminal in fallback_terminals]
        else:
            terminals = [("all", terminal) for terminal in fallback_terminals]

    for label, terminal in terminals:
        if not terminal or terminal.approval_status != "approved":
            continue
        payload = build_face_device_add_user_payload(
            person,
            terminal=terminal,
            effect_time=grant.valid_from,
            end_time=grant.valid_until,
            max_pass_count=1,
            pass_count_cycle=0,
            is_visitor=True,
        )
        queue_face_device_action(
            terminal=terminal,
            action="add_user",
            request_payload=payload,
            requested_by=requested_by,
        )
        queued[label] += 1
        queued["total"] += 1
    return queued


def mark_device_sync_pending(reason: str = ""):
    jobs = DeviceSyncJob.objects.all()
    for job in jobs:
        job.last_status = "pending"
        if reason:
            job.last_error = reason[:1000]
        job.save(update_fields=["last_status", "last_error", "modified_at"])


def _serialize_person(person, *, terminal: GateTerminal | None = None, active_visitor_grant: VisitorFaceAccessGrant | None = None):
    occupancies = person.occupancies.select_related("unit__property__site").filter(is_active=True, is_deleted=False)
    residences = [
        " - ".join([
            occ.unit.property.site.name if occ.unit and occ.unit.property and occ.unit.property.site else "",
            occ.unit.property.name if occ.unit and occ.unit.property else "",
            occ.unit.unit_code if occ.unit else "",
        ]).strip(" -")
        for occ in occupancies
        if occ.unit
    ]
    residences = [value for value in residences if value]
    is_visitor = active_visitor_grant is not None
    has_active_occupancy = bool(residences)
    visitor_valid_until = active_visitor_grant.valid_until.isoformat() if active_visitor_grant and active_visitor_grant.valid_until else ""
    return {
        "id": str(person.id),
        "full_name": person.full_name,
        "phone": person.phone or "",
        "email": person.email or "",
        "id_number": person.id_number or "",
        "card_number": person.card_number or "",
        "photo_url": _build_inline_photo_data_uri(getattr(person, "photo", None)),
        "photo_review_attempt_url": build_photo_display_url(getattr(person, "photo_review_attempt", None)),
        "access_expires_on": _short_date(person.access_expires_on),
        "face_provider": person.face_provider or "",
        "face_subject_id": person.face_subject_id or "",
        "face_enrollment_status": person.face_enrollment_status or "not_started",
        "face_enrollment_status_display": person.get_face_enrollment_status_display() if person.face_enrollment_status else "",
        "photo_review_status": person.photo_review_status or "not_started",
        "photo_review_status_display": person.get_photo_review_status_display() if person.photo_review_status else "",
        "photo_similarity_score": str(person.photo_similarity_score) if person.photo_similarity_score is not None else "",
        "facial_recognition_enabled": bool(person.facial_recognition_enabled),
        "is_visitor": is_visitor,
        "face_user_type": person.face_user_type if person.face_user_type is not None else "",
        "face_access_password": person.face_access_password or "",
        "face_pass_rule_id": person.face_pass_rule_id or "",
        "face_tts_name": person.face_tts_name or "",
        "face_effective_from": person.face_effective_from.isoformat() if person.face_effective_from else "",
        "face_valid_until": visitor_valid_until,
        "face_group_name": _resolve_face_group_name(
            person=person,
            terminal=terminal,
            is_visitor=is_visitor,
            has_active_occupancy=has_active_occupancy,
        ),
        "face_max_pass_count": person.face_max_pass_count if person.face_max_pass_count is not None else "",
        "face_pass_count_cycle": person.face_pass_count_cycle if person.face_pass_count_cycle is not None else "",
        "last_seen": person.last_seen.isoformat() if person.last_seen else "",
        "residences": residences,
        "photo_updated_at": person.modified_at.isoformat() if person.modified_at else "",
        "modified_at": person.modified_at.isoformat() if person.modified_at else "",
    }


def _serialize_unit(unit):
    property_obj = unit.property
    site = property_obj.site if property_obj else None
    return {
        "id": str(unit.id),
        "site": site.name if site else "",
        "property": property_obj.name if property_obj else "",
        "unit_code": unit.unit_code,
        "unit_type": unit.unit_type,
        "status": unit.status,
        "permissions": unit.permissions,
        "is_active": bool(unit.is_active),
        "modified_at": unit.modified_at.isoformat() if unit.modified_at else "",
    }


def _person_is_active_and_eligible(person):
    today = timezone.now().date()
    if getattr(person, "access_expires_on", None) and today > person.access_expires_on:
        return False
    if not getattr(person, "facial_recognition_enabled", False):
        return False
    if getattr(person, "face_enrollment_status", "") not in {"approved", "synced"}:
        return False
    has_active_blacklist = Blacklist.objects.filter(
        person=person,
        is_active=True,
        is_deleted=False,
    ).filter(
        Q(blacklisted_until__isnull=True) | Q(blacklisted_until__gte=timezone.now())
    ).exists()
    if has_active_blacklist:
        return False
    return True


def build_sync_payload(device_identifier, since_cursor, max_items=None):
    now = timezone.now()
    terminal = GateTerminal.objects.filter(serial_number=device_identifier).first()
    people_qs = Person.objects.select_related().filter(modified_at__gt=since_cursor) if since_cursor else Person.objects.all()
    units_qs = Unit.objects.select_related("property__site").filter(modified_at__gt=since_cursor) if since_cursor else Unit.objects.all()
    visitor_grants = (
        VisitorFaceAccessGrant.objects.select_related("person")
        .filter(
            status__in=["approved", "active"],
            valid_from__lte=now,
            valid_until__gte=now,
        )
        .filter(Q(entry_terminal=terminal) | Q(exit_terminal=terminal) if terminal else Q())
        if terminal
        else VisitorFaceAccessGrant.objects.none()
    )
    visitor_grants_by_person_id = {grant.person_id: grant for grant in visitor_grants}

    approved_people = []
    revoked_people = []
    for person in people_qs:
        serialized = _serialize_person(person, terminal=terminal, active_visitor_grant=visitor_grants_by_person_id.get(person.id))
        eligible = _person_is_active_and_eligible(person)
        serialized["sync_state"] = "approved" if eligible else "revoked"
        if eligible:
            approved_people.append(serialized)
        else:
            revoked_people.append(serialized)

    units = [_serialize_unit(unit) for unit in units_qs]

    truncated = False
    if max_items is not None:
        max_items = max(0, int(max_items))
        truncated = any(len(items) > max_items for items in (approved_people, revoked_people, units))
        approved_people = approved_people[:max_items]
        revoked_people = revoked_people[:max_items]
        units = units[:max_items]

    return {
        "device_identifier": device_identifier,
        "cursor": since_cursor.isoformat() if since_cursor else "",
        "next_cursor": now.isoformat(),
        "server_time": now.isoformat(),
        "approved_people": approved_people,
        "revoked_people": revoked_people,
        "units": units,
        "counts": {
            "approved_people": len(approved_people),
            "revoked_people": len(revoked_people),
            "units": len(units),
        },
        "truncated": truncated,
        "max_items": max_items if max_items is not None else "",
    }, now


@api_view(["GET"])
@permission_classes([AllowAny])
def device_changes(request):
    forbidden = _require_device_or_staff(request)
    if forbidden:
        return forbidden

    device_identifier = (request.query_params.get("device_identifier") or "").strip()
    if not device_identifier:
        return Response({"success": False, "error": "device_identifier is required."}, status=status.HTTP_400_BAD_REQUEST)

    cursor = _parse_cursor(request.query_params.get("cursor"))
    job, _ = DeviceSyncJob.objects.get_or_create(device_identifier=device_identifier, defaults={"device_name": request.query_params.get("device_name", "")})
    if request.query_params.get("device_name") and request.query_params.get("device_name") != job.device_name:
        job.device_name = request.query_params.get("device_name") or job.device_name
        job.save(update_fields=["device_name", "modified_at"])

    payload, next_cursor = build_sync_payload(job.device_identifier, cursor)
    job.cursor_at = next_cursor
    job.last_synced_at = timezone.now()
    job.last_status = "success"
    job.last_error = ""
    job.last_payload = payload
    job.save(update_fields=["cursor_at", "last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])

    return Response({"success": True, "payload": payload})


@api_view(["POST"])
@permission_classes([AllowAny])
def device_sync_ack(request):
    forbidden = _require_device_or_staff(request)
    if forbidden:
        return forbidden

    device_identifier = (request.data.get("device_identifier") or "").strip()
    if not device_identifier:
        return Response({"success": False, "error": "device_identifier is required."}, status=status.HTTP_400_BAD_REQUEST)

    job = get_object_or_404(DeviceSyncJob, device_identifier=device_identifier)
    job.last_synced_at = timezone.now()
    job.last_status = "success"
    job.last_error = ""
    job.last_payload = dict(request.data)
    cursor = _parse_cursor(request.data.get("cursor"))
    if cursor:
        job.cursor_at = cursor
    job.save(update_fields=["cursor_at", "last_synced_at", "last_status", "last_error", "last_payload", "modified_at"])

    AuditTrail.objects.create(
        action="edit",
        performed_by=request.user if request.user.is_authenticated else None,
        details=f"Device sync acknowledged for {device_identifier}",
    )
    return Response({"success": True})
