"""
Create a Security group with grants_workflow_access=True and assign units to it.
People in those units will get the same workflow access (Operator role) as +15551234567.

Usage:
  python manage.py setup_security_group_workflow_access
  python manage.py setup_security_group_workflow_access --from-phone +15551234567
  python manage.py setup_security_group_workflow_access --units A-101,B-201
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from GateCore.models import Group, UnitGroupMembership, Occupancy
from GateCore.models.people import Person


class Command(BaseCommand):
    help = "Create Security group with workflow access and assign units (e.g. from phone +15551234567)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            type=str,
            default="Security",
            help="Group name (default: Security)",
        )
        parser.add_argument(
            "--code",
            type=str,
            default="SECURITY",
            help="Group code (default: SECURITY)",
        )
        parser.add_argument(
            "--from-phone",
            type=str,
            default="+15551234567",
            help="Add all units where this phone number has an occupancy (default: +15551234567)",
        )
        parser.add_argument(
            "--units",
            type=str,
            default=None,
            help="Comma-separated unit codes to add (e.g. A-101,B-201). Overrides --from-phone if set.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without creating/updating",
        )

    def handle(self, *args, **options):
        name = options["name"]
        code = options["code"]
        from_phone = options["from_phone"]
        unit_codes_str = options["units"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write("[DRY RUN]")

        # 1) Create or get group and set grants_workflow_access
        group = Group.objects.filter(name=name).first()
        if not group:
            if dry_run:
                self.stdout.write(self.style.WARNING(f"Would create group: {name} (code={code}, grants_workflow_access=True)"))
            else:
                group = Group.objects.create(
                    name=name,
                    code=code,
                    description="Units whose occupants get workflow (Operator) access on mobile login.",
                    grants_workflow_access=True,
                )
                self.stdout.write(self.style.SUCCESS(f"Created group: {group.name} (grants_workflow_access=True)"))
        else:
            if not group.grants_workflow_access:
                if dry_run:
                    self.stdout.write(self.style.WARNING(f"Would set grants_workflow_access=True on group: {group.name}"))
                else:
                    group.grants_workflow_access = True
                    group.save(update_fields=["grants_workflow_access"])
                    self.stdout.write(self.style.SUCCESS(f"Set grants_workflow_access=True on group: {group.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Group already exists with workflow access: {group.name}"))

        # 2) Resolve units to add
        unit_ids = []
        if unit_codes_str:
            codes = [c.strip() for c in unit_codes_str.split(",") if c.strip()]
            from GateCore.models import Unit
            for c in codes:
                units = list(Unit.objects.filter(unit_code__iexact=c, is_active=True, is_deleted=False))
                unit_ids.extend([u.id for u in units])
            unit_ids = list(dict.fromkeys(unit_ids))
            self.stdout.write(f"Resolved {len(unit_ids)} unit(s) from codes: {codes}")
        elif from_phone:
            phone = (from_phone or "").strip()
            if phone:
                from GateCore.services.mobile_auth import normalize_phone, phone_numbers_equal
                normalized = normalize_phone(phone)
                if not normalized:
                    self.stdout.write(self.style.WARNING(f"Could not normalize phone: {from_phone}"))
                else:
                    persons = list(Person.objects.filter(is_active=True, is_deleted=False))
                    matching = [p for p in persons if phone_numbers_equal(p.phone, normalized)]
                    if not matching:
                        self.stdout.write(self.style.WARNING(f"No person found with phone: {from_phone}"))
                    else:
                        for p in matching:
                            occs = Occupancy.objects.filter(
                                person=p, is_active=True, is_deleted=False
                            ).values_list("unit_id", flat=True).distinct()
                            unit_ids.extend(occs)
                        unit_ids = list(dict.fromkeys(unit_ids))
                        self.stdout.write(f"From phone {from_phone}: {len(unit_ids)} unit(s) where that person has occupancy")
            else:
                self.stdout.write(self.style.WARNING("Invalid --from-phone"))
        else:
            self.stdout.write(self.style.WARNING("Specify --from-phone or --units"))

        # 3) Add units to group
        if not group:
            return
        added = 0
        skipped = 0
        for uid in unit_ids:
            if dry_run:
                exists = UnitGroupMembership.objects.filter(unit_id=uid, group=group).exists()
                if exists:
                    skipped += 1
                else:
                    added += 1
                continue
            _, created = UnitGroupMembership.objects.get_or_create(
                unit_id=uid,
                group=group,
                defaults={"notes": "Added via setup_security_group_workflow_access"},
            )
            if created:
                added += 1
            else:
                skipped += 1

        if dry_run:
            self.stdout.write(f"[DRY RUN] Would add {added} unit(s), {skipped} already in group.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Done: {added} unit(s) added to {group.name}, {skipped} already in group."))
        self.stdout.write("People in those units will get Operator (workflow) role on mobile login.")
