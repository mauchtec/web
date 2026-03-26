from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import AccessCredential, AccessPermission, Blacklist, GuestRegistration, VisitorFaceAccessGrant
from GateCore.api_views.residence_bookings import _build_face_enrollment_link, _infer_booking_kind
from GateCore.services.mobile_auth import build_photo_display_url


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def access_credential_detail(request, credential_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    credential = get_object_or_404(AccessCredential.objects.select_related("person"), id=credential_id)
    return Response({
        "credential": {
            "id": str(credential.id),
            "credential_value": credential.credential_value,
            "credential_type": credential.credential_type,
            "credential_type_display": credential.get_credential_type_display(),
            "person": {
                "id": str(credential.person.id) if credential.person else "",
                "full_name": credential.person.full_name if credential.person else "",
            },
            "issued_at": credential.issued_at.isoformat() if credential.issued_at else "",
            "issued_at_display": credential.issued_at.strftime("%Y-%m-%d %H:%M") if credential.issued_at else "",
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else "",
            "expires_at_display": credential.expires_at.strftime("%Y-%m-%d %H:%M") if credential.expires_at else "",
            "last_used": credential.last_used.isoformat() if credential.last_used else "",
            "last_used_display": credential.last_used.strftime("%Y-%m-%d %H:%M") if credential.last_used else "",
            "is_temporary": bool(credential.is_temporary),
            "notes": credential.notes or "",
            "status_label": "Active" if credential.is_active and not credential.is_deleted else "Inactive",
        },
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def access_permission_detail(request, perm_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    perm = get_object_or_404(
        AccessPermission.objects.select_related("person", "access_point", "schedule_rule"),
        id=perm_id,
    )
    return Response({
        "permission": {
            "id": str(perm.id),
            "person": {
                "id": str(perm.person.id) if perm.person else "",
                "full_name": perm.person.full_name if perm.person else "",
            },
            "access_point": {
                "id": str(perm.access_point.id) if perm.access_point else "",
                "name": perm.access_point.name if perm.access_point else "",
            },
            "schedule_rule": {
                "id": str(perm.schedule_rule.id) if perm.schedule_rule else "",
                "name": perm.schedule_rule.name if perm.schedule_rule else "",
            },
            "schedule_display": perm.schedule_rule.name if perm.schedule_rule else "Anytime",
            "valid_from": perm.valid_from.isoformat() if perm.valid_from else "",
            "valid_from_display": perm.valid_from.strftime("%Y-%m-%d %H:%M") if perm.valid_from else "",
            "valid_until": perm.valid_until.isoformat() if perm.valid_until else "",
            "valid_until_display": perm.valid_until.strftime("%Y-%m-%d %H:%M") if perm.valid_until else "",
            "max_daily_uses": perm.max_daily_uses,
            "current_daily_uses": perm.current_daily_uses,
            "priority": perm.priority,
            "status_label": "Active" if perm.is_active and not perm.is_deleted else "Inactive",
            "schedule_override": perm.schedule_override or {},
            "detail_url": reverse("gatecore_access_permission_detail", args=[perm.id]),
        },
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def guest_registration_detail(request, guest_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    guest = get_object_or_404(
        GuestRegistration.objects.select_related("host", "guest", "unit", "approved_by", "vehicle"),
        id=guest_id,
    )
    visitor_face_grant = (
        VisitorFaceAccessGrant.objects.select_related("person", "guest_registration")
        .filter(guest_registration=guest)
        .order_by("-created_at")
        .first()
    )
    return Response({
        "guest": {
            "id": str(guest.id),
            "host": {
                "id": str(guest.host.id) if guest.host else "",
                "full_name": guest.host.full_name if guest.host else "",
            },
            "guest_person": {
                "id": str(guest.guest.id) if guest.guest else "",
                "full_name": guest.guest.full_name if guest.guest else guest.visitor_full_name or "",
                "photo_url": build_photo_display_url(getattr(guest.guest, "photo", None)) if guest.guest else "",
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
            "face_enrollment_status": guest.guest.face_enrollment_status if guest.guest else "not_started",
            "face_enrollment_status_display": guest.guest.get_face_enrollment_status_display() if guest.guest and guest.guest.face_enrollment_status else "",
            "photo_review_status": guest.guest.photo_review_status if guest.guest else "not_started",
            "photo_review_status_display": guest.guest.get_photo_review_status_display() if guest.guest and guest.guest.photo_review_status else "",
            "face_enrollment_link": _build_face_enrollment_link(guest, booking_kind=_infer_booking_kind(guest)),
            "face_valid_from": visitor_face_grant.valid_from.isoformat() if visitor_face_grant and visitor_face_grant.valid_from else "",
            "face_valid_from_display": visitor_face_grant.valid_from.strftime("%Y-%m-%d %H:%M") if visitor_face_grant and visitor_face_grant.valid_from else "",
            "face_valid_until": visitor_face_grant.valid_until.isoformat() if visitor_face_grant and visitor_face_grant.valid_until else "",
            "face_valid_until_display": visitor_face_grant.valid_until.strftime("%Y-%m-%d %H:%M") if visitor_face_grant and visitor_face_grant.valid_until else "",
            "face_grant_status": visitor_face_grant.status if visitor_face_grant else "",
        },
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def blacklist_detail(request, entry_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    entry = get_object_or_404(Blacklist.objects.select_related("person", "vehicle", "credential", "reported_by"), id=entry_id)
    return Response({
        "entry": {
            "id": str(entry.id),
            "person": {
                "id": str(entry.person.id) if entry.person else "",
                "full_name": entry.person.full_name if entry.person else "",
            },
            "vehicle": {
                "id": str(entry.vehicle.id) if entry.vehicle else "",
                "license_plate": entry.vehicle.license_plate if entry.vehicle else "",
            },
            "credential": {
                "id": str(entry.credential.id) if entry.credential else "",
                "credential_value": entry.credential.credential_value if entry.credential else "",
            },
            "target_type": entry.target_type,
            "target_type_display": entry.get_target_type_display(),
            "reason": entry.reason,
            "reason_display": entry.get_reason_display(),
            "details": entry.details or "",
            "reported_by": entry.reported_by.username if entry.reported_by else "",
            "blacklisted_from": entry.blacklisted_from.isoformat() if entry.blacklisted_from else "",
            "blacklisted_from_display": entry.blacklisted_from.strftime("%Y-%m-%d %H:%M") if entry.blacklisted_from else "",
            "blacklisted_until": entry.blacklisted_until.isoformat() if entry.blacklisted_until else "",
            "blacklisted_until_display": entry.blacklisted_until.strftime("%Y-%m-%d %H:%M") if entry.blacklisted_until else "",
            "detail_url": reverse("gatecore_blacklist_detail", args=[entry.id]),
        },
    })
