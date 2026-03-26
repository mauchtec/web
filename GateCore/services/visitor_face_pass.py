from datetime import timedelta

from django.db import OperationalError, transaction
from django.utils import timezone

from GateCore.api_views.device_sync import queue_visitor_face_grant_sync
from GateCore.models import GuestRegistration, VisitorFaceAccessGrant


def _active_guest_registration_for_person(person):
    now = timezone.now()
    try:
        return (
            GuestRegistration.objects.select_related("unit", "unit__property", "unit__property__site")
            .filter(
                guest=person,
                status="approved",
                expected_departure__gte=now,
            )
            .order_by("expected_departure", "-approved_at", "-created_at")
            .first()
        )
    except OperationalError:
        return None


def activate_visitor_face_grant_for_person(person, *, requested_by=None):
    guest_registration = _active_guest_registration_for_person(person)
    if not guest_registration:
        return {"activated": False, "reason": "no_active_guest_registration", "grant": None, "queued": {"entry": 0, "exit": 0, "total": 0}}

    now = timezone.now()
    valid_from = now - timedelta(minutes=5)
    valid_until = now + timedelta(hours=24)
    if guest_registration.expected_departure:
        valid_until = min(valid_until, guest_registration.expected_departure + timedelta(minutes=5))

    try:
        with transaction.atomic():
            grant = (
                VisitorFaceAccessGrant.objects.select_for_update()
                .filter(
                    guest_registration=guest_registration,
                    person=person,
                    status__in=["pending", "approved", "active"],
                )
                .order_by("-created_at")
                .first()
            )
            if grant is None:
                grant = VisitorFaceAccessGrant.create_for_guest_registration(
                    guest_registration,
                    notes="Auto-created from approved visitor face enrollment.",
                )

            entry_terminal, exit_terminal = VisitorFaceAccessGrant.resolve_terminals_for_guest_registration(guest_registration)
            grant.entry_terminal = entry_terminal
            grant.exit_terminal = exit_terminal
            grant.valid_from = valid_from
            grant.valid_until = valid_until
            grant.status = "active"
            grant.save(
                update_fields=[
                    "entry_terminal",
                    "exit_terminal",
                    "valid_from",
                    "valid_until",
                    "status",
                    "modified_at",
                ]
            )
    except OperationalError:
        return {"activated": False, "reason": "grant_table_unavailable", "grant": None, "queued": {"entry": 0, "exit": 0, "total": 0}}

    person.face_effective_from = valid_from
    person.access_expires_on = valid_until.date()
    person.face_max_pass_count = 1
    person.face_pass_count_cycle = 0
    person.save(update_fields=["face_effective_from", "access_expires_on", "face_max_pass_count", "face_pass_count_cycle", "modified_at"])

    queued = queue_visitor_face_grant_sync(grant, requested_by=requested_by)
    return {"activated": True, "reason": "ok", "grant": grant, "queued": queued}
