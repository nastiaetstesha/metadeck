# metadeck/session/consumers.py
import json
import random

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from django.core.cache import cache


CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 часов


def flips_cache_key(session_id: str) -> str:
    return f"metadeck:session:{session_id}:flips"


class SessionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a session room.

    - Lazy model loading via apps.get_model
    - DB calls wrapped with sync_to_async
    - Broadcasts full "state" payload after each action
    - Syncs flip state:
        action: "flip" {card_id, flipped}
        server stores flips in cache + broadcasts flip to group
        state includes flips so reconnect/new join sees correct side
    """

    # ---------- model getters (lazy) ----------
    @staticmethod
    def _Session():
        return apps.get_model("session", "Session")

    @staticmethod
    def _SessionEvent():
        return apps.get_model("session", "SessionEvent")

    @staticmethod
    def _Card():
        return apps.get_model("cards", "Card")

    # ---------- cache helpers (sync is ok here) ----------
    def get_flips(self) -> dict:
        return cache.get(flips_cache_key(str(self.session_id)), {}) or {}

    def set_flips(self, flips: dict) -> None:
        cache.set(flips_cache_key(str(self.session_id)), flips or {}, CACHE_TTL_SECONDS)

    def set_flip(self, card_id: str, flipped: bool) -> dict:
        flips = self.get_flips()
        flips[str(card_id)] = bool(flipped)
        self.set_flips(flips)
        return flips

    def clear_flips(self) -> None:
        self.set_flips({})

    def prune_flips(self, allowed_ids: list[str]) -> dict:
        allowed = {str(x) for x in (allowed_ids or [])}
        current = self.get_flips()
        pruned = {cid: bool(current.get(cid, False)) for cid in allowed}
        self.set_flips(pruned)
        return pruned

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"session_{self.session_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        payload = await self.build_state_payload()
        await self.send_json(payload)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data or "{}")
        action = data.get("action")

        if action == "draw_one":
            await self.draw_and_broadcast(count=1)
            return
        
        if action == "draw_three":
            await self.draw_and_broadcast(count=3)
            return

        if action == "draw_six":
            await self.draw_and_broadcast(count=6)
            return

        if action == "reset":
            await self.reset_and_broadcast()
            return

        if action == "flip":
            card_id = data.get("card_id")
            flipped = data.get("flipped")
            if card_id is None or flipped is None:
                return

            card_id = str(card_id)
            flipped = bool(flipped)

            # ✅ ВАЖНО: flip разрешаем только для текущих drawn_ids
            drawn_ids = await self.get_current_drawn_ids()
            if card_id not in set(map(str, drawn_ids)):
                return

            self.set_flip(card_id, flipped)

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "flip.message",
                    "card_id": card_id,
                    "flipped": flipped,
                },
            )
            return

    async def draw_and_broadcast(self, count: int):
        drawn_ids = await self.draw_cards(count=count)
        await self.save_draw_event(drawn_ids)

        # ✅ очищаем/обрезаем flips под новую раздачу
        self.prune_flips(drawn_ids)

        payload = await self.build_state_payload()
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "session.message", "payload": payload},
        )

    async def reset_and_broadcast(self):
        await self.save_draw_event([])
        self.clear_flips()

        payload = await self.build_state_payload()
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "session.message", "payload": payload},
        )

    async def session_message(self, event):
        await self.send_json(event["payload"])

    async def flip_message(self, event):
        await self.send_json(
            {
                "type": "flip",
                "card_id": event["card_id"],
                "flipped": event["flipped"],
            }
        )

    async def send_json(self, payload: dict):
        await self.send(text_data=json.dumps(payload))

    # ---------- DB helpers ----------
    @sync_to_async
    def draw_cards(self, count: int):
        Session = self._Session()
        Card = self._Card()

        session = Session.objects.select_related("deck").get(id=self.session_id)

        ids = list(
            Card.objects.filter(deck=session.deck, is_active=True).values_list("id", flat=True)
        )
        random.shuffle(ids)
        return [str(i) for i in ids[:count]]

    @sync_to_async
    def save_draw_event(self, drawn_ids):
        Session = self._Session()
        SessionEvent = self._SessionEvent()

        session = Session.objects.get(id=self.session_id)
        return SessionEvent.objects.create(
            session=session,
            event_type="draw",
            payload={"drawn_ids": drawn_ids},
        )

    @sync_to_async
    def get_current_drawn_ids(self) -> list[str]:
        """Нужен для валидации flip (flip только по текущим картам)."""
        Session = self._Session()
        SessionEvent = self._SessionEvent()

        session = Session.objects.get(id=self.session_id)
        last = (
            SessionEvent.objects.filter(session=session, event_type="draw")
            .order_by("-created_at")
            .first()
        )
        return (last.payload.get("drawn_ids", []) if last else [])

    @sync_to_async
    def build_state_payload(self):
        Session = self._Session()
        SessionEvent = self._SessionEvent()
        Card = self._Card()

        session = Session.objects.select_related("deck").get(id=self.session_id)
        deck = session.deck

        last = (
            SessionEvent.objects.filter(session=session, event_type="draw")
            .order_by("-created_at")
            .first()
        )
        drawn_ids = (last.payload.get("drawn_ids", []) if last else [])

        cards = list(Card.objects.filter(id__in=drawn_ids))
        cards_map = {str(c.id): c for c in cards}

        back_url = ""
        if getattr(deck, "back_full", None):
            try:
                back_url = deck.back_full.url
            except Exception:
                back_url = ""

        items = []
        for cid in drawn_ids:
            c = cards_map.get(str(cid))
            if not c:
                continue

            front_url = ""
            if getattr(c, "image_full", None):
                try:
                    front_url = c.image_full.url
                except Exception:
                    front_url = ""

            items.append(
                {
                    "id": str(cid),
                    "front_url": front_url,
                    "back_url": back_url,
                }
            )

        # ✅ flips: берём из cache, режем по drawn_ids и ПИШЕМ ОБРАТНО (чтобы cache не разрастался)
        flips = cache.get(flips_cache_key(str(self.session_id)), {}) or {}
        allowed = {str(x) for x in drawn_ids}
        flips_pruned = {cid: bool(flips.get(cid, False)) for cid in allowed}
        cache.set(flips_cache_key(str(self.session_id)), flips_pruned, CACHE_TTL_SECONDS)

        return {
            "type": "state",
            "mode": session.mode,
            "cards": items,
            "flips": flips_pruned,
        }
