import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser, BaseParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta, time

from GateCore.models import GuestRegistration, Occupancy, Person
from GateCore.services.pin_generator import generate_unique_pin
from GateCore.services.mobile_auth import normalize_phone


class TextJSONParser(BaseParser):
    media_type = "text/plain"

    def parse(self, stream, media_type=None, parser_context=None):
        raw = stream.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)


def _require_resident(request):
    person = getattr(request.user, "person_profile", None)
    if not person:
        return Response({"detail": "Resident profile not found."}, status=status.HTTP_403_FORBIDDEN)
    return person


def _booking_payload(guest: GuestRegistration, *, request=None):
    booking_kind = _infer_booking_kind(guest)
    return {
        "id": str(guest.id),
        "booking_kind": booking_kind,
        "host": {
            "id": str(guest.host.id) if guest.host else "",
            "full_name": guest.host.full_name if guest.host else "",
        },
        "guest_person": {
            "id": str(guest.guest.id) if guest.guest else "",
            "full_name": guest.guest.full_name if guest.guest else guest.visitor_full_name or "",
            "phone": guest.guest.phone if guest.guest else guest.visitor_phone or "",
        },
        "unit": {
            "id": str(guest.unit.id) if guest.unit else "",
            "unit_code": guest.unit.unit_code if guest.unit else "",
        },
        "vehicle": {
            "id": str(guest.vehicle.id) if guest.vehicle else "",
            "license_plate": guest.vehicle.license_plate if guest.vehicle else "",
        },
        "expected_arrival": guest.expected_arrival.isoformat() if guest.expected_arrival else "",
        "expected_arrival_display": guest.expected_arrival.strftime("%Y-%m-%d %H:%M") if guest.expected_arrival else "",
        "expected_departure": guest.expected_departure.isoformat() if guest.expected_departure else "",
        "expected_departure_display": guest.expected_departure.strftime("%Y-%m-%d %H:%M") if guest.expected_departure else "",
        "actual_arrival": guest.actual_arrival.isoformat() if guest.actual_arrival else "",
        "actual_arrival_display": guest.actual_arrival.strftime("%Y-%m-%d %H:%M") if guest.actual_arrival else "",
        "actual_departure": guest.actual_departure.isoformat() if guest.actual_departure else "",
        "actual_departure_display": guest.actual_departure.strftime("%Y-%m-%d %H:%M") if guest.actual_departure else "",
        "purpose": guest.purpose or "",
        "notes": guest.notes or "",
        "status": guest.status,
        "status_display": guest.get_status_display(),
        "approved_by": guest.approved_by.username if guest.approved_by else "",
        "approved_at": guest.approved_at.isoformat() if guest.approved_at else "",
        "approved_at_display": guest.approved_at.strftime("%Y-%m-%d %H:%M") if guest.approved_at else "",
        "temporary_pin": guest.temporary_pin or "",
        "pin_expires_at": guest.pin_expires_at.isoformat() if guest.pin_expires_at else "",
        "pin_expires_at_display": guest.pin_expires_at.strftime("%Y-%m-%d %H:%M") if guest.pin_expires_at else "",
        "face_enrollment_link": _build_face_enrollment_link(guest, booking_kind=booking_kind, request=request),
        "detail_url": reverse("residence_booking_detail_api", args=[guest.id]),
    }


def _active_host_unit(person):
    occupancy = (
        Occupancy.objects.select_related("unit")
        .filter(person=person, is_active=True, is_deleted=False)
        .order_by("-is_primary", "-start_date")
        .first()
    )
    return occupancy.unit if occupancy else None


def _split_name(full_name: str):
    parts = [part for part in str(full_name or "").strip().split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], "Guest"
    return parts[0], " ".join(parts[1:])


def _infer_booking_kind(guest: GuestRegistration):
    purpose = str(guest.purpose or "").strip().lower()
    duration_hours = None
    if guest.expected_arrival and guest.expected_departure:
        duration = guest.expected_departure - guest.expected_arrival
        duration_hours = duration.total_seconds() / 3600.0

    if purpose == "delivery / collection":
        return "delivery_collection"
    if purpose == "group booking":
        return "group_booking"
    if purpose in {"visitor face invite", "visitor facial", "face invite", "face enrollment invite"}:
        return "visitor_face_invite"
    if "visitor" in purpose and "face" in purpose:
        return "visitor_face_invite"
    if purpose == "future booking" or (duration_hours is not None and duration_hours > 24.5):
        return "future_booking"
    if purpose == "invite contact":
        return "invite_contact"
    if purpose == "invite cellphone":
        return "invite_phone"
    return "invite_phone" if duration_hours is None or duration_hours <= 24.5 else "future_booking"


def _build_face_enrollment_link(guest: GuestRegistration, *, booking_kind: str = "", request=None):
    kind = (booking_kind or _infer_booking_kind(guest)).strip().lower()
    if kind != "visitor_face_invite":
        return ""

    base = str(getattr(settings, "VISITOR_FACE_ENROLLMENT_URL_BASE", "") or "").strip()
    if not base and request is not None:
        base = request.build_absolute_uri(reverse("visitor_face_enrollment"))
    if not base:
        return ""

    parsed = urlsplit(base)
    path = parsed.path or ""
    if path.endswith("/api/gatecore/public/visitor-face-invite/"):
        path = reverse("visitor_face_enrollment")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "booking_id": str(guest.id),
            "guest_id": str(guest.guest_id or ""),
            "guest_phone": str(getattr(guest.guest, "phone", "") or ""),
            "pin": str(guest.temporary_pin or ""),
        }
    )
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query), parsed.fragment))


def _parse_datetime_or_date(value: str, *, end_of_day: bool = False):
    raw = str(value or "").strip()
    if not raw:
        return None

    if len(raw) == 10 and "T" not in raw:
        parsed_date = datetime.strptime(raw, "%Y-%m-%d").date()
        dt = datetime.combine(parsed_date, time(23, 59, 0) if end_of_day else time(0, 0, 0))
        return timezone.make_aware(dt, timezone.get_current_timezone())

    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=0, microsecond=0)
    return parsed


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bookings_overview(request):
    person = _require_resident(request)
    if isinstance(person, Response):
        return person

    bookings = (
        GuestRegistration.objects.select_related("host", "guest", "unit", "vehicle", "approved_by")
        .filter(host=person)
        .order_by("-expected_arrival")
    )
    rows = [_booking_payload(guest, request=request) for guest in bookings]
    return Response({"rows": rows, "bookings": rows})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, FormParser, MultiPartParser, TextJSONParser])
def create_booking(request):
    person = _require_resident(request)
    if isinstance(person, Response):
        return person

    booking_kind = str(request.data.get("booking_kind") or "invite_phone").strip().lower()
    unit = _active_host_unit(person)
    if not unit:
        return Response({"detail": "No active unit found for resident."}, status=status.HTTP_400_BAD_REQUEST)

    if booking_kind not in {"invite_contact", "invite_phone", "future_booking", "delivery_collection", "group_booking", "visitor_face_invite"}:
        return Response({"detail": "Invalid booking_kind."}, status=status.HTTP_400_BAD_REQUEST)

    guest_name = str(request.data.get("guest_name") or "").strip()
    guest_phone = normalize_phone(request.data.get("guest_phone"))
    end_date = request.data.get("end_date")
    purpose = str(request.data.get("purpose") or "").strip()
    notes = str(request.data.get("notes") or "").strip()

    now = timezone.now()
    if booking_kind == "future_booking":
        if not end_date:
            return Response({"detail": "end_date is required for future bookings."}, status=status.HTTP_400_BAD_REQUEST)
        departure_dt = _parse_datetime_or_date(end_date, end_of_day=True)
        if not departure_dt:
            return Response({"detail": "end_date must be a valid date."}, status=status.HTTP_400_BAD_REQUEST)
        arrival_dt = now
        if departure_dt <= arrival_dt:
            return Response({"detail": "End date must be after the current time."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        arrival_dt = now
        departure_dt = now + timedelta(hours=24)

    if booking_kind in {"invite_contact", "invite_phone", "group_booking", "visitor_face_invite"} and (not guest_name or not guest_phone):
        return Response(
            {"detail": "guest_name and guest_phone are required for invited bookings."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if booking_kind == "delivery_collection":
        guest_name = guest_name or "Delivery / Collection"

    if booking_kind == "visitor_face_invite":
        purpose = "Visitor face invite"

    guest = Person.objects.filter(phone=guest_phone, is_active=True, is_deleted=False).first() if guest_phone else None
    if not guest:
        first_name, last_name = _split_name(guest_name)
        guest = Person.objects.create(
            first_name=first_name or guest_name,
            last_name=last_name or "Guest",
            phone=guest_phone or f"000{abs(hash((guest_name, now.isoformat()))) % 1000000:06d}",
            email="",
        )

    booking = GuestRegistration.objects.create(
        host=person,
        guest=guest,
        unit=unit,
        expected_arrival=arrival_dt,
        expected_departure=departure_dt,
        purpose=purpose or {
            "invite_contact": "Invite contact",
            "invite_phone": "Invite cellphone",
            "future_booking": "Future booking",
            "delivery_collection": "Delivery / collection",
            "group_booking": "Group booking",
            "visitor_face_invite": "Visitor face invite",
        }[booking_kind],
        notes=notes,
        status="approved",
        approved_by=request.user,
        approved_at=now,
        temporary_pin=generate_unique_pin(),
        pin_expires_at=departure_dt,
    )
    return Response({"booking": _booking_payload(booking, request=request)}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_detail(request, booking_id):
    person = _require_resident(request)
    if isinstance(person, Response):
        return person

    booking = get_object_or_404(
        GuestRegistration.objects.select_related("host", "guest", "unit", "vehicle", "approved_by"),
        id=booking_id,
        host=person,
    )
    return Response({"booking": _booking_payload(booking, request=request)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_booking(request, booking_id):
    person = _require_resident(request)
    if isinstance(person, Response):
        return person

    booking = get_object_or_404(GuestRegistration.objects.select_related("host"), id=booking_id, host=person)
    if booking.status in {"cancelled", "completed", "rejected"}:
        return Response({"booking": _booking_payload(booking, request=request)})

    booking.status = "cancelled"
    booking.save(update_fields=["status", "modified_at"])
    return Response({"booking": _booking_payload(booking, request=request)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_booking_pin(request, booking_id):
    person = _require_resident(request)
    if isinstance(person, Response):
        return person

    booking = get_object_or_404(GuestRegistration.objects.select_related("host"), id=booking_id, host=person)
    booking.temporary_pin = ""
    booking.pin_expires_at = None
    booking.status = "cancelled"
    booking.save(update_fields=["temporary_pin", "pin_expires_at", "status", "modified_at"])
    return Response({"booking": _booking_payload(booking, request=request)})
