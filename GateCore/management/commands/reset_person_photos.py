from django.core.management.base import BaseCommand, CommandError

from GateCore.models import Person


PHOTO_RESET_FIELDS = {
    "photo": None,
    "photo_review_attempt": None,
    "face_provider": "",
    "face_subject_id": "",
    "face_enrollment_status": "not_started",
    "face_enrollment_quality_score": None,
    "face_enrolled_at": None,
    "face_last_synced_at": None,
    "face_enrollment_error": "",
    "face_reference_image_id": "",
    "photo_review_status": "not_started",
    "photo_similarity_score": None,
    "photo_reviewed_at": None,
    "photo_review_error": "",
    "facial_recognition_enabled": False,
}


class Command(BaseCommand):
    help = "Clear all resident photo files and reset photo/face review state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm that all resident photos should be cleared.",
        )

    def handle(self, *args, **options):
        if not options.get("yes"):
            raise CommandError("Refusing to clear resident photos without --yes.")

        updated_count = 0
        deleted_files = 0
        errors = []

        for person in Person.objects.all().iterator():
            changed = False
            for field_name in ("photo", "photo_review_attempt"):
                field_file = getattr(person, field_name, None)
                if not field_file:
                    continue
                if getattr(field_file, "name", ""):
                    try:
                        field_file.delete(save=False)
                        deleted_files += 1
                    except Exception as exc:
                        errors.append(f"{person.id}:{field_name}:{exc}")
                setattr(person, field_name, None)
                changed = True

            for field_name, reset_value in PHOTO_RESET_FIELDS.items():
                if field_name in ("photo", "photo_review_attempt"):
                    continue
                if getattr(person, field_name) != reset_value:
                    setattr(person, field_name, reset_value)
                    changed = True

            if changed:
                person.save(
                    update_fields=[
                        "photo",
                        "photo_review_attempt",
                        "face_provider",
                        "face_subject_id",
                        "face_enrollment_status",
                        "face_enrollment_quality_score",
                        "face_enrolled_at",
                        "face_last_synced_at",
                        "face_enrollment_error",
                        "face_reference_image_id",
                        "photo_review_status",
                        "photo_similarity_score",
                        "photo_reviewed_at",
                        "photo_review_error",
                        "facial_recognition_enabled",
                        "modified_at",
                    ]
                )
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared resident photos for {updated_count} people and deleted {deleted_files} image files."
            )
        )
        if errors:
            self.stdout.write(self.style.WARNING("Some files could not be deleted:"))
            for item in errors[:20]:
                self.stdout.write(self.style.WARNING(f"  {item}"))
