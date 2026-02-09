from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.apps import apps


class Command(BaseCommand):
    help = "Delete sessions and events older than N days (default: 7)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **opts):
        days = opts["days"]
        cutoff = timezone.now() - timedelta(days=days)

        Session = apps.get_model("session", "Session")
        SessionEvent = apps.get_model("session", "SessionEvent")

        # если SessionEvent FK с CASCADE — достаточно удалить Session
        old_sessions = Session.objects.filter(created_at__lt=cutoff)
        count_sessions = old_sessions.count()

        # на всякий случай можно подчистить events отдельно (если не CASCADE)
        count_events = SessionEvent.objects.filter(created_at__lt=cutoff).count()
        SessionEvent.objects.filter(created_at__lt=cutoff).delete()

        old_sessions.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Deleted sessions: {count_sessions}, deleted events: {count_events} (older than {days} days)"
        ))
