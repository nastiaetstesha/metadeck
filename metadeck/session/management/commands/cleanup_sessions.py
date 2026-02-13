# metadeck/session/management/commands/cleanup_sessions.py
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from session.models import Session, SessionEvent


class Command(BaseCommand):
    help = "Delete sessions and session events older than N days (default: 5)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=5,
            help="Delete objects older than this many days (default: 5).",
        )
        parser.add_argument(
            "--only-inactive",
            action="store_true",
            help="Delete only inactive sessions (is_active=False).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not delete anything, only print what would be deleted.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        only_inactive = options["only_inactive"]
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timedelta(days=days)

        sessions_qs = Session.objects.filter(created_at__lt=cutoff)
        if only_inactive:
            sessions_qs = sessions_qs.filter(is_active=False)

        events_qs = SessionEvent.objects.filter(created_at__lt=cutoff)

        sessions_count = sessions_qs.count()
        events_count = events_qs.count()

        self.stdout.write(
            self.style.NOTICE(
                f"Cutoff: {cutoff.isoformat()} | sessions: {sessions_count} | events: {events_count}"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: nothing deleted."))
            return

        # 1) Удаляем старые сессии (events удалятся каскадом)
        deleted_sessions = sessions_qs.delete()

        # 2) На всякий случай удаляем оставшиеся старые events
        deleted_events = events_qs.delete()

        self.stdout.write(self.style.SUCCESS(f"Deleted sessions: {deleted_sessions}"))
        self.stdout.write(self.style.SUCCESS(f"Deleted events: {deleted_events}"))
