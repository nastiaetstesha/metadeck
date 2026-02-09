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

    - Lazy model loading via apps.get_model (prevents "apps aren't loaded yet" at import time)
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

    # ---------- cache helpers ----------
    def get_flips(self) -> dict:
        return cache.get(flips_cache_key(self.session_id), {}) or {}

    def set_flips(self, flips: dict) -> None:
        cache.set(flips_cache_key(self.session_id), flips or {}, CACHE_TTL_SECONDS)

    def set_flip(self, card_id: str, flipped: bool) -> dict:
        flips = self.get_flips()
        flips[str(card_id)] = bool(flipped)
        self.set_flips(flips)
        return flips

    def clear_flips(self) -> None:
        self.set_flips({})

    def prune_flips(self, allowed_ids: list[str]) -> dict:
        """
        Оставляем flip-состояния только для текущих drawn_ids.
        Для новых id добавляем False.
        """
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

        # send current state to this client
        payload = await self.build_state_payload()
        await self.send_json(payload)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data or "{}")
        action = data.get("action")

        if action == "draw_one":
            await self.draw_and_broadcast(count=1)
        elif action == "draw_six":
            await self.draw_and_broadcast(count=6)
        elif action == "reset":
            await self.reset_and_broadcast()
        elif action == "flip":
            card_id = data.get("card_id")
            flipped = data.get("flipped")
            if card_id is None or flipped is None:
                return

            # сохраняем состояние переворота
            self.set_flip(str(card_id), bool(flipped))

            # рассылаем всем участникам flip-событие
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "flip.message",
                    "card_id": str(card_id),
                    "flipped": bool(flipped),
                },
            )

    async def draw_and_broadcast(self, count: int):
        drawn_ids = await self.draw_cards(count=count)
        await self.save_draw_event(drawn_ids)

        # flips: очищаем/обрезаем под новую раздачу, чтобы не тянуть старые
        self.prune_flips(drawn_ids)

        payload = await self.build_state_payload()
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "session.message", "payload": payload},
        )

    async def reset_and_broadcast(self):
        await self.save_draw_event([])

        # при reset сбрасываем flips
        self.clear_flips()

        payload = await self.build_state_payload()
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "session.message", "payload": payload},
        )

    async def session_message(self, event):
        await self.send_json(event["payload"])

    async def flip_message(self, event):
        # точечное событие (без полного ререндера)
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
    def build_state_payload(self):
        """
        Full state for rendering:
        - ordered drawn_ids from last "draw" event
        - urls for fronts + back (deck back)
        - flips from cache (so reconnect/new join sees correct side)
        """
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
            c = cards_map.get(cid)
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
                    "id": cid,
                    "front_url": front_url,
                    "back_url": back_url,
                }
            )

        flips = cache.get(flips_cache_key(str(self.session_id)), {}) or {}
        # на всякий случай: оставим flips только для текущих drawn_ids
        allowed = {str(x) for x in drawn_ids}
        flips = {cid: bool(flips.get(cid, False)) for cid in allowed}

        return {
            "type": "state",
            "mode": session.mode,
            "cards": items,
            "flips": flips,
        }
