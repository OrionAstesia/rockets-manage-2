"""首页（规格 §8.2）。前台全部只读，不提供任何表单。"""

from django.db.models import Count
from django.views.generic import TemplateView

from ops.models import FlightLog, Save
from spaceflight.models import CraftType, Spacecraft

RECENT_FLIGHT_COUNT = 5


class HomeView(TemplateView):
    """近期发射 5 条 + 在役航天器按类型计数 + 存档列表。"""

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # 按计划日期降序；planned_date 为空的排在最后（SQLite 下 NULL 最小，DESC 自然靠后）
        ctx["recent_flights"] = (
            FlightLog.objects.select_related("rocket", "site")
            .order_by("-planned_date")[:RECENT_FLIGHT_COUNT]
        )
        ctx["spacecraft_counts"] = self.spacecraft_counts()
        ctx["saves"] = Save.objects.all()
        return ctx

    @staticmethod
    def spacecraft_counts():
        """在役航天器按 craft_type 分组计数，如「空间站 2 · 中继卫星 3 · 探测器 1」。"""
        labels = dict(CraftType.choices)
        rows = (
            Spacecraft.objects.filter(is_active=True)
            .values("craft_type")
            .annotate(total=Count("id"))
            .order_by("-total", "craft_type")
        )
        counts = [
            {"label": labels.get(row["craft_type"], row["craft_type"]), "total": row["total"]}
            for row in rows
        ]
        return {"rows": counts, "total": sum(row["total"] for row in counts)}
