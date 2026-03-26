from django.core.management.base import BaseCommand

from face_devices.services import cleanup_expired_visitor_face_grants


class Command(BaseCommand):
    help = "Expire visitor face grants, queue terminal user removal, and disable unused visitor face access."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be expired without making changes.",
        )

    def handle(self, *args, **options):
        result = cleanup_expired_visitor_face_grants(dry_run=options["dry_run"])
        prefix = "[DRY RUN] " if result["dry_run"] else ""
        self.stdout.write(f"{prefix}Expired visitor grants: {result['expired_grants']}")
        self.stdout.write(f"{prefix}Delete actions queued: {result['delete_actions_queued']}")
        self.stdout.write(f"{prefix}People facial access disabled: {result['people_disabled']}")
        self.stdout.write(self.style.SUCCESS("Done."))
