from django.contrib import admin
from .models import Deck, Card


class CardInline(admin.TabularInline):
    model = Card
    extra = 0
    fields = ("position", "title", "code", "image_preview", "image_full", "is_active")
    ordering = ("position",)
    show_change_link = True


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title",)
    inlines = [CardInline]


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("id", "deck", "position", "title", "code", "is_active", "created_at")
    list_filter = ("deck", "is_active")
    search_fields = ("title", "code", "deck__title")
    ordering = ("deck", "position", "id")
