from django.urls import path
from . import views

app_name = "cards"

urlpatterns = [
    path("", views.home, name="home"),
    path("deck/<int:deck_id>/", views.deck_modes, name="deck_modes"),
]
