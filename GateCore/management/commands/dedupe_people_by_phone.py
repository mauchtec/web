"""
Dedupe Person records by phone number.

This project historically allowed duplicate Person.phone values (and mixed formats like 065... vs +27...).
Android OTP login expects a stable identity, so duplicates cause random membership selection and 403s.

This command:
- finds all Person rows matching the given phone (normalized comparison)
- chooses a canonical Person (prefers: has linked user, then has active occupancies, then oldest)
- re-points related records to the canonical Person
- deletes the duplicate Person rows

Usage:
  python manage.py dedupe_people_by_phone 0656231093
  python manage.py dedupe_people_by_phone +27656231093 --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from GateCore.models import (
    AccessCredential,
    AccessLog,
    AccessPermission,
    AuditTrail,
    Blacklist,
    GuestRegistration,
    Occupancy,
    ScheduleRule,
    SMSDeliveryLog,
    Vehicle,
)
from GateCore.models.people import Person
from GateCore.services.mobile_auth import normalize_phone, phone_numbers_equal


def _active_occupancy_count(person: Person) -> int:
    return Occupancy.objects.filter(person=person, is_active=True, is_deleted=False).count()


def _pick_canonical(people: list[Person]) -> Person:
    # Prefer linked user, then most active occupancies, then oldest created_at.
    def sort_key(p: Person):
        return (
            0 if p.user_id else 1,
            -_active_occupancy_count(p),
            p.created_at,
        )

    return sorted(people, key=sort_key)[0]


def _safe_repoint_queryset(qs, field_name: str, canonical: Person, dry_run: bool, stdout):
    if dry_run:
        count = qs.count()
        if count:
            stdout.write(f"  [DRY RUN] Would repoint {count} record(s) of {qs.model.__name__}.{field_name} -> {canonical.id}")
        return
    qs.update(**{field_name: canonical})


class Command(BaseCommand):
    help = "Deduplicate Person records by phone number, repointing related records."

    def add_arguments(self, parser):
        parser.add_argument("phone", type=str, help="Phone number to dedupe (e.g. 0656231093, +27...)")
        parser.add_argument("--dry-run", action="store_true", help="Show actions without changing data")

    def handle(self, *args, **options):
        raw = (options["phone"] or "").strip()
        dry_run = bool(options["dry_run"])
        normalized = normalize_phone(raw)
        if not normalized:
            self.stdout.write(self.style.ERROR(f"Could not normalize phone: {raw!r}"))
            return

        people = [p for p in Person.objects.all() if phone_numbers_equal(p.phone, normalized)]
        if len(people) <= 1:
            self.stdout.write(self.style.SUCCESS(f"No duplicates found for {normalized}. Matches={len(people)}"))
            return

        canonical = _pick_canonical(people)
        duplicates = [p for p in people if p.id != canonical.id]

        self.stdout.write(f"Phone: {raw} normalized={normalized}")
        self.stdout.write(f"Canonical: {canonical.id} {canonical.full_name} stored_phone={canonical.phone!r} user={bool(canonical.user_id)} activeOcc={_active_occupancy_count(canonical)}")
        self.stdout.write(f"Duplicates: {len(duplicates)}")
        for d in duplicates:
            self.stdout.write(f" - {d.id} {d.full_name} stored_phone={d.phone!r} user={bool(d.user_id)} activeOcc={_active_occupancy_count(d)}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only. No changes will be made."))

        with transaction.atomic():
            # Ensure canonical has the normalized phone without triggering model-level unique validation mid-dedupe.
            if not dry_run and canonical.phone != normalized:
                Person.objects.filter(id=canonical.id).update(phone=normalized)

            for dup in duplicates:
                # If duplicate has a linked user and canonical doesn't, move it.
                if dup.user_id and not canonical.user_id:
                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would move user {dup.user_id} from {dup.id} -> {canonical.id}")
                    else:
                        Person.objects.filter(id=canonical.id).update(user_id=dup.user_id)
                        Person.objects.filter(id=dup.id).update(user_id=None)

                # Simple FKs
                _safe_repoint_queryset(Vehicle.objects.filter(person=dup), "person", canonical, dry_run, self.stdout)
                _safe_repoint_queryset(AccessCredential.objects.filter(person=dup), "person", canonical, dry_run, self.stdout)
                _safe_repoint_queryset(AccessLog.objects.filter(person=dup), "person", canonical, dry_run, self.stdout)
                _safe_repoint_queryset(SMSDeliveryLog.objects.filter(person=dup), "person", canonical, dry_run, self.stdout)
                _safe_repoint_queryset(AuditTrail.objects.filter(person=dup), "person", canonical, dry_run, self.stdout)
                _safe_repoint_queryset(ScheduleRule.objects.filter(visitor=dup), "visitor", canonical, dry_run, self.stdout)

                # GuestRegistration host/guest
                _safe_repoint_queryset(GuestRegistration.objects.filter(host=dup), "host", canonical, dry_run, self.stdout)
                _safe_repoint_queryset(GuestRegistration.objects.filter(guest=dup), "guest", canonical, dry_run, self.stdout)

                # AccessPermission has unique_together(person, access_point)
                for perm in AccessPermission.objects.filter(person=dup):
                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would repoint AccessPermission {perm.id} -> {canonical.id}")
                        continue
                    perm.person = canonical
                    try:
                        perm.save(update_fields=["person"])
                    except IntegrityError:
                        # Canonical already has permission for that access_point.
                        perm.delete()

                # Occupancy has unique_together(person, unit, role)
                for occ in Occupancy.objects.filter(person=dup):
                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would repoint Occupancy {occ.id} -> {canonical.id}")
                        continue
                    occ.person = canonical
                    try:
                        occ.save(update_fields=["person"])
                    except IntegrityError:
                        # Canonical already has this occupancy. Drop the duplicate row.
                        occ.is_active = False
                        occ.is_deleted = True
                        occ.save(update_fields=["is_active", "is_deleted"])

                # Blacklist rows may already exist; keep canonical and delete dup rows on conflict
                for bl in Blacklist.objects.filter(person=dup):
                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would repoint Blacklist {bl.id} -> {canonical.id}")
                        continue
                    bl.person = canonical
                    try:
                        bl.save(update_fields=["person"])
                    except IntegrityError:
                        bl.delete()

                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would delete duplicate Person {dup.id}")
                else:
                    dup.delete()

        self.stdout.write(self.style.SUCCESS(f"Done. Kept canonical {canonical.id}. Deleted {len(duplicates)} duplicate(s)."))

