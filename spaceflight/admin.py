"""Admin：发射场与在轨航天器（规格 §8.1）。"""

from django.contrib import admin

from core.admin import ProtectedDeleteMixin

from .models import Site, Spacecraft


@admin.register(Site)
class SiteAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = [
        "name", "program", "body", "latitude", "longitude", "max_mass", "is_operational",
    ]
    list_filter = ["body", "is_operational"]
    search_fields = ["name"]


@admin.register(Spacecraft)
class SpacecraftAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "craft_type", "situation", "body", "is_active"]
    list_filter = ["craft_type", "body", "situation", "is_active"]
    search_fields = ["name"]
