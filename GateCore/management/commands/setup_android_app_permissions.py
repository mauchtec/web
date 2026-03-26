"""
Step 3: Register Android app(s) for the group and grant Group Access Permissions.
Run: python manage.py setup_android_app_permissions [--group-name "Android App Group"] [--app-name "Gate Access App"]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from GateCore.models import Group, AndroidApp, GroupAccessPermission, AccessPoint


class Command(BaseCommand):
    help = "Register Android app for group and grant group access permissions (Step 3)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--group-name",
            type=str,
            default="Android App Group",
            help="Group name to use (default: Android App Group)",
        )
        parser.add_argument(
            "--app-name",
            type=str,
            default="Gate Access App",
            help="Android app name to register (default: Gate Access App)",
        )
        parser.add_argument(
            "--device-id",
            type=str,
            default=None,
            help="Device identifier for the app (optional; a placeholder is used if not set)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without creating",
        )

    def handle(self, *args, **options):
        group_name = options["group_name"]
        app_name = options["app_name"]
        device_id = options["device_id"] or "android-app-default"
        dry_run = options["dry_run"]

        # 1) Get group
        group = Group.objects.filter(name=group_name).first()
        if not group:
            self.stdout.write(self.style.ERROR(f"Group not found: {group_name}. Run setup_android_app_group first."))
            return

        # 2) Register Android app and assign to group
        if dry_run:
            self.stdout.write(f"[DRY RUN] Would register Android app: {app_name} (device_id={device_id}) in group {group.name}")
        else:
            app, created = AndroidApp.objects.get_or_create(
                device_identifier=device_id,
                defaults={
                    "name": app_name,
                    "group": group,
                    "device_token": "",
                    "app_version": "1.0",
                    "notes": "Registered via setup_android_app_permissions (Step 3)",
                },
            )
            if not created:
                if app.group_id != group.id:
                    app.group = group
                    app.save(update_fields=["group"])
                    self.stdout.write(self.style.SUCCESS(f"Updated app {app.name} to group {group.name}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Android app already exists: {app.name} in {group.name}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Registered Android app: {app.name} in group {group.name}"))

        # 3) Grant Group Access Permissions for all access points
        access_points = list(AccessPoint.objects.filter(is_active=True, is_deleted=False))
        if not access_points:
            self.stdout.write(self.style.WARNING("No active access points found. Create access points (e.g. via insert_demo_data) then re-run."))
            return

        added = 0
        skipped = 0
        for ap in access_points:
            if dry_run:
                exists = GroupAccessPermission.objects.filter(group=group, access_point=ap).exists()
                if exists:
                    self.stdout.write(f"  [DRY RUN] Permission already exists: {group.name} -> {ap.name}")
                    skipped += 1
                else:
                    self.stdout.write(f"  [DRY RUN] Would grant: {group.name} -> {ap.name}")
                    added += 1
                continue
            _, created = GroupAccessPermission.objects.get_or_create(
                group=group,
                access_point=ap,
                defaults={
                    "valid_from": timezone.now(),
                    "valid_until": None,
                    "max_daily_uses": 0,
                    "priority": 1,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Granted: {group.name} -> {ap.name}"))
                added += 1
            else:
                skipped += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Step 3 complete: {added} group permission(s) added, {skipped} already existed."))
        else:
            self.stdout.write(f"[DRY RUN] Would add {added} permission(s), {skipped} already exist.")
