from django.shortcuts import get_object_or_404, render
from .models import Deck
from session.models import SessionMode


def home(request):
    decks = Deck.objects.filter(is_active=True).order_by("title")
    return render(request, "cards/home.html", {"decks": decks})


def deck_modes(request, deck_id):
    deck = get_object_or_404(Deck, id=deck_id, is_active=True)
    return render(request, "cards/deck_modes.html", {"deck": deck, "modes": SessionMode.choices})
