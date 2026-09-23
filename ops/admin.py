"""Admin：存档与发射日志（规格 §8.1）。"""

from django.contrib import admin, messages
from django.db.models import ProtectedError

from core.admin import ProtectedDeleteMixin

from .models import FlightLog, Save


@admin.register(Save)
class SaveAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "game_mode", "start_date"]
    list_filter = ["game_mode"]
    search_fields = ["name"]

    def get_deleted_objects(self, objs, request):
        """删存档时不再把「PROTECT 引用」算成无法删除。

        `Save.delete()` 会先级联清掉自己的在轨航天器与发射日志（规格 §4.11），
        而 Django 的 Admin 在确认页之前会独立跑一遍删除收集器，看到 `protected`
        非空就直接拒绝删除 —— 于是删存档的入口会被自己挡死。这里把 protected
        置空（其余三项照旧），让确认页正常列出将被删除的内容。

        安全性：Save 的子表只有 Rocket/Payload/Site/Spacecraft/FlightLog，其中
        唯一会以 PROTECT 引用兄弟子表的就是 FlightLog，正是 `Save.delete()` 先清掉的那张表。
        """
        to_delete, model_count, perms_needed, _protected = super().get_deleted_objects(
            objs, request
        )
        return to_delete, model_count, perms_needed, []

    def delete_queryset(self, request, queryset):
        """批量删除动作绕过 `Model.delete()`，这里逐个调用来复用同一套级联顺序。"""
        for save in queryset:
            try:
                save.delete()
            except ProtectedError as exc:
                self.message_user(request, self._protected_message(exc), level=messages.ERROR)


@admin.register(FlightLog)
class FlightLogAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "state", "planned_date", "actual_date", "rocket", "site"]
    list_filter = ["program", "state", "site"]
    search_fields = ["name"]
    date_hierarchy = "planned_date"
