from django.db import models


class Deck(models.Model):
    """A deck of metaphorical cards."""
    title = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    # back side of the deck (card back)
    back_preview = models.ImageField(upload_to="decks/back/preview/", blank=True, null=True)
    back_full = models.ImageField(upload_to="decks/back/full/", blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Card(models.Model):
    """A single card inside a deck."""
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name="cards")

    title = models.CharField(max_length=120, blank=True)
    # Optional unique code inside the deck (useful later)
    code = models.CharField(max_length=50, blank=True)

    image_preview = models.ImageField(upload_to="cards/preview/")
    image_full = models.ImageField(upload_to="cards/full/")

    # optional ordering inside deck
    position = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["deck", "position", "id"]
        indexes = [
            models.Index(fields=["deck", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["deck", "code"],
                name="unique_card_code_in_deck",
                condition=models.Q(code__gt=""),
            )
        ]

    def __str__(self):
        if self.title:
            return f"{self.deck.title}: {self.title}"
        return f"{self.deck.title}: card #{self.id}"
