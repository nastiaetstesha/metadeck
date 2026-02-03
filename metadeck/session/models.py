import uuid
from django.db import models

from cards.models import Deck, Card


class SessionMode(models.TextChoices):
    RANDOM_ONE = "random_one", "1 random card"
    PICK_ONE_OF_SIX = "pick_one_of_six", "Pick 1 of 6"
    PAST_PRESENT_FUTURE = "past_present_future", "Past-Present-Future (3)"
    RESOURCE_BLOCK_ACTION = "resource_block_action", "Resource-Block-Action (3)"
    EMOTION_WHEEL_PLUS_CARD = "emotion_plus_card", "Emotion + Card"
    BLIND_CHOICE = "blind_choice", "Blind choice"


class Session(models.Model):
    """A real-time room for psychologist + client."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    deck = models.ForeignKey(Deck, on_delete=models.PROTECT, related_name="sessions")
    mode = models.CharField(max_length=32, choices=SessionMode.choices)

    title = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.deck.title} | {self.mode} | {self.id}"


class SessionEventType(models.TextChoices):
    DRAW = "draw", "draw"
    PICK = "pick", "pick"
    FLIP = "flip", "flip"
    RESET = "reset", "reset"


class SessionEvent(models.Model):
    """History of actions inside a session (useful for syncing + audit)."""
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=16, choices=SessionEventType.choices)

    # cards involved in this event
    cards = models.ManyToManyField(Card, blank=True)

    # For cases like "pick one card"
    chosen_card = models.ForeignKey(
        Card, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # Store extra info (positions, who clicked, etc.)
    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["session", "event_type"]),
        ]

    def __str__(self):
        return f"{self.session_id} | {self.event_type} | {self.created_at}"
