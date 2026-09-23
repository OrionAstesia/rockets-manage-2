"""Admin：所有写操作都在这里（规格 §8.1）。前台只读。"""

from django.contrib import admin

from core.admin import ProtectedDeleteMixin

from .models import Payload, Rocket, RocketStage


class RocketStageInline(admin.TabularInline):
    """级在火箭表单里增删（规格 §3 约束 2、§8.1）—— 前台不提供级的编辑界面。"""

    model = RocketStage
    extra = 1
    ordering = ["stage_order"]


@admin.register(Rocket)
class RocketAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "program", "series", "manufacturer", "crew_capacity", "is_reusable"]
    list_filter = ["program", "series", "is_reusable"]
    search_fields = ["name"]
    inlines = [RocketStageInline]


@admin.register(RocketStage)
class RocketStageAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = [
        "rocket", "stage_order", "engine", "engine_count",
        "fuel_tank", "tank_count", "structure_mass", "separation_type",
    ]
    list_filter = ["separation_type", "rocket"]
    search_fields = ["rocket__name"]


@admin.register(Payload)
class PayloadAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = [
        "name", "program", "payload_type", "mass",
        "crew_capacity", "has_docking_port", "cost",
    ]
    list_filter = ["program", "payload_type"]
    search_fields = ["name"]
