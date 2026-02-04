from django.urls import path
from . import views


app_name = "session"

urlpatterns = [
    path("create/", views.create_session, name="create"),
    path("<uuid:session_id>/", views.room, name="room"),
    path("<uuid:session_id>/draw1/", views.draw_one, name="draw_one"),
    path("<uuid:session_id>/draw6/", views.draw_six, name="draw_six"),
]
