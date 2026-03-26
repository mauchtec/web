from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from face_devices.models import FaceDeviceAccessLog


def _parse_event_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        seconds = number / 1000.0 if number > 9999999999 else number
        try:
            return datetime.fromtimestamp(seconds, tz=dt_timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            try:
                number = int(text)
                seconds = number / 1000.0 if number > 9999999999 else number
                return datetime.fromtimestamp(seconds, tz=dt_timezone.utc)
            except Exception:
                return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
        return parsed if parsed.tzinfo else timezone.make_aware(parsed, dt_timezone.utc)
    return None


class Command(BaseCommand):
    help = "Backfill FaceDeviceAccessLog.event_time from payload fields like recog_time."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show counts without writing changes.")
        parser.add_argument("--limit", type=int, default=0, help="Optional max rows to process (0 = all).")

    def handle(self, *args, **options):
        dry_run: bool = bool(options.get("dry_run"))
        limit: int = int(options.get("limit") or 0)

        queryset = FaceDeviceAccessLog.objects.order_by("created_at")
        if limit > 0:
            queryset = queryset[:limit]

        scanned = 0
        updated = 0
        skipped = 0

        for row in queryset.iterator():
            scanned += 1
            payload = row.payload if isinstance(row.payload, dict) else {}
            parsed = None
            for key in ("recog_time", "event_time", "record_time", "verify_time", "timestamp", "ts", "create_time", "check_time"):
                parsed = _parse_event_time(payload.get(key))
                if parsed is not None:
                    break
            if parsed is None:
                skipped += 1
                continue
            if row.event_time == parsed:
                skipped += 1
                continue
            updated += 1
            if not dry_run:
                row.event_time = parsed
                row.save(update_fields=["event_time", "modified_at"])

        mode = "DRY-RUN" if dry_run else "APPLIED"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} backfill complete: scanned={scanned} updated={updated} skipped={skipped}"
            )
        )

