from django.contrib import admin, messages
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Body


class ProtectedDeleteMixin:
    """把 PROTECT 外键导致的删除失败转成友好提示，避免 500（规格 §4.12）。

    标准路径下 Django 的 ``get_deleted_objects()`` 已能拦住 PROTECT 并显示
    「无法删除」页面；本 mixin 兜住它挡不住的边界情况：确认页与提交之间新增的
    关联对象，以及批量删除动作直接抛出的 ``ProtectedError``。
    """

    @staticmethod
    def _protected_message(exc):
        names = "、".join(str(obj) for obj in exc.protected_objects[:5])
        more = " 等" if len(exc.protected_objects) > 5 else ""
        return f"删除失败：仍有受保护的下级数据引用它（{names}{more}），请先处理这些数据。"

    def _changelist_url(self):
        opts = self.model._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    def delete_view(self, request, object_id, extra_context=None):
        try:
            return super().delete_view(request, object_id, extra_context)
        except ProtectedError as exc:
            self.message_user(request, self._protected_message(exc), level=messages.ERROR)
            return HttpResponseRedirect(self._changelist_url())

    def delete_queryset(self, request, queryset):
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError as exc:
            self.message_user(request, self._protected_message(exc), level=messages.ERROR)


@admin.register(Body)
class BodyAdmin(ProtectedDeleteMixin, admin.ModelAdmin):
    list_display = ["name", "mu", "radius", "has_atmosphere"]
    search_fields = ["name"]
    list_filter = ["has_atmosphere"]
