# metadeck/session/consumers.py
import json
import random
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from cards.models import Card
from .models import Session, SessionEvent, SessionEventType


class SessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"session_{self.session_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # При подключении — отправим текущее состояние из БД
        state = await self.get_current_state()
        await self.send_json({"type": "state", **state})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")

        if action == "draw_one":
            drawn_ids = await self.draw_cards(count=1)
            await self.save_draw_event(drawn_ids)
            await self.broadcast_state(drawn_ids)

        if action == "draw_six":
            drawn_ids = await self.draw_cards(count=6)
            await self.save_draw_event(drawn_ids)
            await self.broadcast_state(drawn_ids)

    async def broadcast_state(self, drawn_ids):
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "session.message", "payload": {"type": "state", "drawn_ids": drawn_ids}},
        )

    async def session_message(self, event):
        await self.send_json(event["payload"])

    async def send_json(self, payload: dict):
        await self.send(text_data=json.dumps(payload))

    # -------- DB helpers --------
    @sync_to_async
    def get_current_state(self):
        session = Session.objects.get(id=self.session_id)
        last = session.events.filter(event_type=SessionEventType.DRAW).order_by("-created_at").first()
        if not last:
            return {"drawn_ids": []}
        return {"drawn_ids": last.payload.get("drawn_ids", [])}

    @sync_to_async
    def draw_cards(self, count: int):
        session = Session.objects.get(id=self.session_id)
        ids = list(
            Card.objects.filter(deck=session.deck, is_active=True).values_list("id", flat=True)
        )
        random.shuffle(ids)
        return [str(i) for i in ids[:count]]

    @sync_to_async
    def save_draw_event(self, drawn_ids):
        session = Session.objects.get(id=self.session_id)
        ev = SessionEvent.objects.create(
            session=session,
            event_type=SessionEventType.DRAW,
            payload={"drawn_ids": drawn_ids},
        )
        return ev
