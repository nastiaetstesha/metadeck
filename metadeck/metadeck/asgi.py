# metadeck/metadeck/asgi.py
import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

import session.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "metadeck.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(session.routing.websocket_urlpatterns)
        ),
    }
)

# ✅ В DEBUG оборачиваем ВЕСЬ application, а не django_asgi_app
if settings.DEBUG:
    application = ASGIStaticFilesHandler(application)
