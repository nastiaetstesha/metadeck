from django.contrib import admin
from .models import Session, SessionEvent


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "deck", "mode", "is_active", "created_at")
    list_filter = ("mode", "is_active", "deck")
    search_fields = ("id", "title", "deck__title")
    ordering = ("-created_at",)


@admin.register(SessionEvent)
class SessionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "event_type", "chosen_card", "created_at")
    list_filter = ("event_type", "session__deck", "session__mode")
    search_fields = ("session__id",)
    ordering = ("-created_at",)
    filter_horizontal = ("cards",)
