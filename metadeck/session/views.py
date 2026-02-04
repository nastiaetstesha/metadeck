import random
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cards.models import Deck, Card
from .models import Session


@require_POST
def create_session(request):
    deck_id = request.POST.get("deck_id")
    mode = request.POST.get("mode")

    deck = get_object_or_404(Deck, id=deck_id, is_active=True)
    session = Session.objects.create(deck=deck, mode=mode)

    return redirect("session:room", session_id=session.id)


def room(request, session_id):
    session = get_object_or_404(Session, id=session_id)

    # client link определяется по параметру k
    k = request.GET.get("k")
    is_client = (k == session.client_key)

    # временный стейт вытянутых карт (пока MVP)
    drawn_ids = request.session.get(f"drawn_{session_id}", [])
    cards = Card.objects.filter(id__in=drawn_ids)
    cards_map = {str(c.id): c for c in cards}
    drawn_cards = [cards_map.get(cid) for cid in drawn_ids if cid in cards_map]

    return render(
        request,
        "session/room.html",
        {
            "session": session,
            "is_client": is_client,
            "drawn_cards": drawn_cards,
            # ссылки показываем только психологу (is_client=False)
            "client_link": request.build_absolute_uri(f"/s/{session.id}/?k={session.client_key}"),
            "host_link": request.build_absolute_uri(f"/s/{session.id}/"),
        },
    )


@require_POST
def draw_one(request, session_id):
    session = get_object_or_404(Session, id=session_id)

    card = (
        Card.objects.filter(deck=session.deck, is_active=True)
        .order_by("?")
        .first()
    )
    request.session[f"drawn_{session_id}"] = [str(card.id)] if card else []
    return redirect("session:room", session_id=session.id)


@require_POST
def draw_six(request, session_id):
    session = get_object_or_404(Session, id=session_id)

    ids = list(
        Card.objects.filter(deck=session.deck, is_active=True)
        .values_list("id", flat=True)
    )
    random.shuffle(ids)
    chosen = [str(i) for i in ids[:6]]
    request.session[f"drawn_{session_id}"] = chosen

    return redirect("session:room", session_id=session.id)
