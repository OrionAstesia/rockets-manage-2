from django.contrib import admin

from core.admin import ProtectedDeleteMixin

from .models import Engine, FuelTank, ScienceInstrument


@admin.register(FuelTank)
class FuelTankAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "fuel_type", "diameter", "dry_mass", "capacity", "cost"]
    list_filter = ["fuel_type"]
    search_fields = ["name"]


@admin.register(Engine)
class EngineAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = [
        "name", "diameter", "dry_mass",
        "thrust_asl", "thrust_vac", "isp_asl", "isp_vac", "cost",
    ]
    list_filter = ["diameter"]
    search_fields = ["name"]


@admin.register(ScienceInstrument)
class ScienceInstrumentAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = [
        "name", "experiment_type", "dry_mass", "data_value",
        "is_repeatable", "requires_crew", "cost",
    ]
    list_filter = ["is_repeatable", "requires_crew"]
    search_fields = ["name"]
