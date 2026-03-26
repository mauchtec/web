from django.core.management.base import BaseCommand

from GateCore.services.face_update import cleanup_expired_pending


class Command(BaseCommand):
    help = "Remove expired/rejected pending face references and their image files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting.",
        )

    def handle(self, *args, **options):
        result = cleanup_expired_pending(dry_run=options["dry_run"])
        prefix = "[DRY RUN] " if result["dry_run"] else ""
        self.stdout.write(
            f"{prefix}Deleted images from soft-deleted refs: {result['deleted_images']}"
        )
        self.stdout.write(
            f"{prefix}Expired pending refs cleaned up: {result['expired_pending']}"
        )
        self.stdout.write(self.style.SUCCESS("Done."))
