from django.urls import re_path
from .consumers import SessionConsumer

websocket_urlpatterns = [
    re_path(r"^ws/s/(?P<session_id>[0-9a-f-]+)/$", SessionConsumer.as_asgi()),
]
