"""
Step 2: Create the Android App group and assign units to it.
Run: python manage.py setup_android_app_group [--name "Android App Group"] [--units A-101,B-201] or [--all-units]
"""
from django.core.management.base import BaseCommand
from GateCore.models import Group, Unit, UnitGroupMembership


class Command(BaseCommand):
    help = "Create Android App group and assign units to it (Step 2)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            type=str,
            default="Android App Group",
            help="Group name (default: Android App Group)",
        )
        parser.add_argument(
            "--code",
            type=str,
            default="ANDROID_APP",
            help="Group code (default: ANDROID_APP)",
        )
        parser.add_argument(
            "--units",
            type=str,
            default=None,
            help="Comma-separated unit codes to add (e.g. A-101,B-201,T-10A)",
        )
        parser.add_argument(
            "--all-units",
            action="store_true",
            help="Add all active units to the group",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without creating/assigning",
        )

    def handle(self, *args, **options):
        name = options["name"]
        code = options["code"]
        unit_codes_str = options["units"]
        all_units = options["all_units"]
        dry_run = options["dry_run"]

        if not unit_codes_str and not all_units:
            self.stdout.write(
                self.style.WARNING(
                    "No units specified. Use --units A-101,B-201 or --all-units to assign units."
                )
            )

        # 1) Create or get group
        if dry_run:
            self.stdout.write(f"[DRY RUN] Would create or get group: {name} (code={code})")
            group = Group.objects.filter(name=name).first()
            if not group:
                group = Group.objects.filter(code=code).first()
        else:
            group, created = Group.objects.get_or_create(
                name=name,
                defaults={
                    "code": code,
                    "description": "Units that can use the Android app for access.",
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {group.name} (code={group.code})"))
            else:
                self.stdout.write(self.style.WARNING(f"Group already exists: {group.name}"))

        if not group and dry_run:
            self.stdout.write("[DRY RUN] No group to assign units to. Exiting.")
            return

        # 2) Resolve units
        if all_units:
            units = list(Unit.objects.filter(is_active=True, is_deleted=False))
            self.stdout.write(f"Found {len(units)} active unit(s) to add.")
        elif unit_codes_str:
            codes = [c.strip() for c in unit_codes_str.split(",") if c.strip()]
            units = []
            for c in codes:
                # unit_code can appear in different properties; take all matches
                found = list(Unit.objects.filter(unit_code__iexact=c, is_active=True, is_deleted=False))
                if not found:
                    self.stdout.write(self.style.WARNING(f"No unit found with code: {c}"))
                else:
                    units.extend(found)
            # deduplicate by id
            seen = set()
            units = [u for u in units if u.id not in seen and not seen.add(u.id)]
            self.stdout.write(f"Resolved {len(units)} unit(s) from codes: {codes}")
        else:
            units = []

        # 3) Assign units to group
        added = 0
        skipped = 0
        for unit in units:
            if dry_run:
                exists = UnitGroupMembership.objects.filter(unit=unit, group=group).exists()
                if exists:
                    self.stdout.write(f"  [DRY RUN] {unit.unit_code} already in group, skip")
                    skipped += 1
                else:
                    self.stdout.write(f"  [DRY RUN] Would add {unit.unit_code} to {group.name}")
                    added += 1
                continue
            _, created = UnitGroupMembership.objects.get_or_create(
                unit=unit,
                group=group,
                defaults={"notes": "Added via setup_android_app_group"},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Added unit {unit.unit_code} to {group.name}"))
                added += 1
            else:
                skipped += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Step 2 complete: {added} unit(s) added to group, {skipped} already in group."))
        else:
            self.stdout.write(f"[DRY RUN] Would add {added} unit(s), {skipped} already in group.")
