from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from GateCore.api_views.device_sync import queue_face_device_delete_user
from GateCore.models import AuditTrail, VisitorFaceAccessGrant


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _serialize_grant(grant: VisitorFaceAccessGrant) -> dict:
    guest_registration = grant.guest_registration
    person = grant.person
    return {
        "id": str(grant.id),
        "status": grant.status,
        "valid_from": grant.valid_from.isoformat() if grant.valid_from else "",
        "valid_until": grant.valid_until.isoformat() if grant.valid_until else "",
        "entry_pass_used": bool(grant.entry_pass_used),
        "exit_pass_used": bool(grant.exit_pass_used),
        "entry_used_at": grant.entry_used_at.isoformat() if grant.entry_used_at else "",
        "exit_used_at": grant.exit_used_at.isoformat() if grant.exit_used_at else "",
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else "",
        "notes": grant.notes or "",
        "person": {
            "id": str(person.id) if person else "",
            "full_name": person.full_name if person else "",
            "phone": person.phone if person else "",
        },
        "guest_registration": {
            "id": str(guest_registration.id) if guest_registration else "",
            "status": guest_registration.status if guest_registration else "",
            "expected_arrival": guest_registration.expected_arrival.isoformat() if guest_registration and guest_registration.expected_arrival else "",
            "expected_departure": guest_registration.expected_departure.isoformat() if guest_registration and guest_registration.expected_departure else "",
            "actual_arrival": guest_registration.actual_arrival.isoformat() if guest_registration and guest_registration.actual_arrival else "",
            "actual_departure": guest_registration.actual_departure.isoformat() if guest_registration and guest_registration.actual_departure else "",
        },
        "entry_terminal": {
            "id": str(grant.entry_terminal.id) if grant.entry_terminal else "",
            "serial_number": grant.entry_terminal.serial_number if grant.entry_terminal else "",
            "display_name": grant.entry_terminal.display_name if grant.entry_terminal else "",
            "direction": grant.entry_terminal.direction if grant.entry_terminal else "",
        },
        "exit_terminal": {
            "id": str(grant.exit_terminal.id) if grant.exit_terminal else "",
            "serial_number": grant.exit_terminal.serial_number if grant.exit_terminal else "",
            "display_name": grant.exit_terminal.display_name if grant.exit_terminal else "",
            "direction": grant.exit_terminal.direction if grant.exit_terminal else "",
        },
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visitor_face_grants_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    rows = [
        _serialize_grant(grant)
        for grant in VisitorFaceAccessGrant.objects.select_related(
            "person", "guest_registration", "entry_terminal", "exit_terminal"
        ).order_by("-created_at")[:500]
    ]
    return Response({"rows": rows, "visitor_face_grants": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visitor_face_grant_detail(request, grant_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    grant = get_object_or_404(
        VisitorFaceAccessGrant.objects.select_related("person", "guest_registration", "entry_terminal", "exit_terminal"),
        id=grant_id,
    )
    return Response({"grant": _serialize_grant(grant)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def visitor_face_grant_revoke(request, grant_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    grant = get_object_or_404(
        VisitorFaceAccessGrant.objects.select_related("person", "guest_registration", "entry_terminal", "exit_terminal"),
        id=grant_id,
    )
    now = timezone.now()

    delete_actions = 0
    if grant.entry_terminal and not grant.entry_pass_used:
        if queue_face_device_delete_user(grant.entry_terminal, grant.person, requested_by=request.user):
            delete_actions += 1
    if grant.exit_terminal and not grant.exit_pass_used:
        if queue_face_device_delete_user(grant.exit_terminal, grant.person, requested_by=request.user):
            delete_actions += 1

    grant.status = "revoked"
    grant.revoked_at = now
    note = f"Manually revoked by {request.user.username} at {now.isoformat()}."
    grant.notes = f"{grant.notes}\n{note}".strip() if grant.notes else note
    grant.save(update_fields=["status", "revoked_at", "notes", "modified_at"])

    other_active_exists = VisitorFaceAccessGrant.objects.filter(
        person=grant.person,
        status__in=["approved", "active"],
        valid_until__gte=now,
    ).exclude(id=grant.id).exists()
    if grant.person.facial_recognition_enabled and not other_active_exists:
        grant.person.facial_recognition_enabled = False
        grant.person.save(update_fields=["facial_recognition_enabled", "modified_at"])

    AuditTrail.objects.create(
        person=grant.person,
        action="visitor_face_grant_revoked",
        performed_by=request.user if request.user.is_authenticated else None,
        details=f"Manually revoked visitor face grant {grant.id}. Delete actions queued: {delete_actions}",
    )

    return Response(
        {
            "success": True,
            "delete_actions_queued": delete_actions,
            "grant": _serialize_grant(grant),
        }
    )
