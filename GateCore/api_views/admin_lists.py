from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import AccessCredential, AccessPermission, Blacklist, GuestRegistration, SMSDeliveryLog, VisitorFaceAccessGrant
from GateCore.api_views.residence_bookings import _build_face_enrollment_link, _infer_booking_kind


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sms_logs_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    logs = SMSDeliveryLog.objects.select_related("unit", "person", "schedule_rule").order_by("-created_at")[:500]
    rows = []
    for log in logs:
        rows.append({
            "id": str(log.id),
            "created_at": log.created_at.isoformat(),
            "created_at_display": log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "status": log.status,
            "status_display": log.get_status_display(),
            "provider": log.provider or "",
            "trigger": log.trigger or "",
            "unit": {
                "id": str(log.unit.id) if log.unit else "",
                "unit_code": log.unit.unit_code if log.unit else "",
            },
            "person": {
                "id": str(log.person.id) if log.person else "",
                "full_name": log.person.full_name if log.person else "",
            },
            "visitor_name": log.visitor_name or "",
            "visitor_phone": log.visitor_phone or "",
            "recipient_phone": log.recipient_phone or "",
            "message": log.message or "",
            "provider_message_id": log.provider_message_id or "",
            "error_message": log.error_message or "",
            "completed_at": log.completed_at.isoformat() if log.completed_at else "",
            "completed_at_display": log.completed_at.strftime("%Y-%m-%d %H:%M:%S") if log.completed_at else "",
            "detail_url": reverse("gatecore_sms_logs"),
        })
    return Response({"sms_logs": rows, "rows": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def access_credentials_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    creds = AccessCredential.objects.select_related("person").order_by("person__last_name", "person__first_name", "-issued_at")
    rows = []
    for cred in creds:
        rows.append({
            "id": str(cred.id),
            "credential_value": cred.credential_value,
            "credential_type": cred.credential_type,
            "credential_type_display": cred.get_credential_type_display(),
            "person": {
                "id": str(cred.person.id) if cred.person else "",
                "full_name": cred.person.full_name if cred.person else "",
            },
            "is_active": bool(cred.is_active),
            "is_deleted": bool(cred.is_deleted),
            "status_label": "Active" if cred.is_active and not cred.is_deleted else "Inactive",
            "detail_url": reverse("gatecore_access_credential_detail", args=[cred.id]),
        })
    return Response({"credentials": rows, "rows": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def access_permissions_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    perms = AccessPermission.objects.select_related("person", "access_point", "schedule_rule").order_by("-priority", "person__last_name")
    rows = []
    for perm in perms:
        rows.append({
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
            "status_label": "Active" if perm.is_active and not perm.is_deleted else "Inactive",
            "detail_url": reverse("gatecore_access_permission_detail", args=[perm.id]),
        })
    return Response({"permissions": rows, "rows": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def guest_registrations_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    guests = GuestRegistration.objects.select_related("guest", "host", "unit", "vehicle").order_by("-expected_arrival")
    visitor_grants = {}
    for grant in VisitorFaceAccessGrant.objects.select_related("guest_registration").filter(guest_registration__in=guests).order_by("-created_at"):
        key = str(grant.guest_registration_id)
        if key not in visitor_grants:
            visitor_grants[key] = grant
    rows = []
    for guest in guests:
        visitor_face_grant = visitor_grants.get(str(guest.id))
        rows.append({
            "id": str(guest.id),
            "guest_name": guest.guest.full_name if guest.guest else guest.visitor_full_name or "",
            "person": {
                "id": str(guest.host.id) if guest.host else "",
                "full_name": guest.host.full_name if guest.host else "",
            },
            "unit": {
                "id": str(guest.unit.id) if guest.unit else "",
                "unit_code": guest.unit.unit_code if guest.unit else "",
            },
            "expected_arrival": guest.expected_arrival.isoformat() if guest.expected_arrival else "",
            "expected_departure": guest.expected_departure.isoformat() if guest.expected_departure else "",
            "expected_arrival_display": guest.expected_arrival.strftime("%Y-%m-%d %H:%M") if guest.expected_arrival else "",
            "expected_departure_display": guest.expected_departure.strftime("%Y-%m-%d %H:%M") if guest.expected_departure else "",
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
            "face_valid_from": visitor_face_grant.valid_from.isoformat() if visitor_face_grant and visitor_face_grant.valid_from else "",
            "face_valid_from_display": visitor_face_grant.valid_from.strftime("%Y-%m-%d %H:%M") if visitor_face_grant and visitor_face_grant.valid_from else "",
            "face_valid_until": visitor_face_grant.valid_until.isoformat() if visitor_face_grant and visitor_face_grant.valid_until else "",
            "face_valid_until_display": visitor_face_grant.valid_until.strftime("%Y-%m-%d %H:%M") if visitor_face_grant and visitor_face_grant.valid_until else "",
            "face_grant_status": visitor_face_grant.status if visitor_face_grant else "",
            "face_enrollment_link": _build_face_enrollment_link(guest, booking_kind=_infer_booking_kind(guest)),
            "detail_url": reverse("gatecore_guest_registration_detail", args=[guest.id]),
        })
    return Response({"guests": rows, "rows": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def blacklist_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    entries = Blacklist.objects.select_related("person", "vehicle", "credential").order_by("-blacklisted_from")
    rows = []
    for entry in entries:
        rows.append({
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
            "blacklisted_from": entry.blacklisted_from.isoformat() if entry.blacklisted_from else "",
            "blacklisted_from_display": entry.blacklisted_from.strftime("%Y-%m-%d") if entry.blacklisted_from else "",
            "blacklisted_until": entry.blacklisted_until.isoformat() if entry.blacklisted_until else "",
            "blacklisted_until_display": entry.blacklisted_until.strftime("%Y-%m-%d") if entry.blacklisted_until else "",
            "detail_url": reverse("gatecore_blacklist_detail", args=[entry.id]),
        })
    return Response({"blacklist": rows, "rows": rows})
