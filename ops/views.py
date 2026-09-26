"""存档各集合的列表页、发射日程与发射日志的增删改（文档 11 第 4.1 节）。

每个集合**独立成页**：一页只显示一张表，二级导航在 `templates/ops/save_base.html` 里。
"""

from django.db.models import Count, F
from django.urls import reverse
from django.views.generic import DetailView, ListView

from core.views import (
    SaveScopedListView,
    ScopedCreateView,
    ScopedDeleteView,
    ScopedUpdateView,
)
from fleet.models import Payload, Rocket
from services.orbital import orbital_period
from spaceflight.models import Site, Spacecraft

from .forms import FlightLogForm
from .models import FlightLog, FlightState, Save


def result_text(flight):
    """结果编码 → 人话（语义见模型 `result_code` 的 help_text）。"""
    if flight.result_code is None:
        return "—"
    if flight.result_code == 0:
        return "成功"
    if flight.result_code == -1:
        return "失败"
    return f"第 {flight.result_code} 级失效"


def period_text(spacecraft):
    """轨道周期**实时算**、不落库（文档 10 第 4.2 节）；算不出来时显示「—」。"""
    seconds, days = orbital_period(
        spacecraft.sma,
        spacecraft.eccentricity,
        spacecraft.body.mu if spacecraft.body_id else None,
    )
    if seconds is None:
        return "—"
    return f"{seconds:,.1f} s · {days:.4f} Kerbin 天"


class WorkspaceView(DetailView):
    """存档工作台 `/saves/<pk>/`。"""

    model = Save
    template_name = "ops/workspace.html"
    context_object_name = "save"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        save = self.object
        ctx["rockets"] = save.rockets.annotate(stage_total=Count("stages"))
        ctx["payloads"] = save.payloads.all()
        ctx["sites"] = save.sites.select_related("body")
        ctx["spacecraft_rows"] = [
            {"obj": sc, "period": period_text(sc)}
            for sc in save.spacecraft.select_related("body")
        ]
        ctx["flight_rows"] = [
            {"obj": flight, "result": result_text(flight)}
            for flight in save.flights.select_related("rocket", "site")
        ]
        return ctx


class SaveRocketsView(SaveScopedListView):
    model = Rocket
    template_name = "ops/save_rockets.html"
    context_object_name = "rockets"
    select_related = ()

    def get_queryset(self):
        # 「级数」列：一次 annotate，避免每行再来一次 count 查询
        return super().get_queryset().annotate(stage_total=Count("stages"))


class SavePayloadsView(SaveScopedListView):
    model = Payload
    template_name = "ops/save_payloads.html"
    context_object_name = "payloads"


class SaveSitesView(SaveScopedListView):
    model = Site
    template_name = "ops/save_sites.html"
    context_object_name = "sites"
    select_related = ("body",)


class SaveSpacecraftView(SaveScopedListView):
    model = Spacecraft
    template_name = "ops/save_spacecraft.html"
    context_object_name = "spacecraft_rows"
    select_related = ("body",)

    def get_queryset(self):
        # 周期实时算、不落库，所以返回带 period 的字典列表（**不要**给这个视图设 paginate_by）
        return [{"obj": sc, "period": period_text(sc)} for sc in super().get_queryset()]


class SaveFlightsView(SaveScopedListView):
    model = FlightLog
    template_name = "ops/save_flights.html"
    context_object_name = "flight_rows"
    select_related = ("rocket", "site")

    def get_queryset(self):
        # 同上：返回字典列表，不要设 paginate_by
        return [{"obj": flight, "result": result_text(flight)} for flight in super().get_queryset()]


class ScheduleView(ListView):
    """发射日程：全存档的待发任务，按计划日期升序（`planned_date` 为空的排最后）。"""

    model = FlightLog
    template_name = "ops/schedule.html"
    context_object_name = "flights"

    def get_queryset(self):
        return (
            FlightLog.objects.filter(state=FlightState.PLANNED)
            .select_related("rocket", "payload", "site")
            .order_by(F("planned_date").asc(nulls_last=True))
        )


class FlightLogCreateView(ScopedCreateView):
    model = FlightLog
    form_class = FlightLogForm


class FlightLogUpdateView(ScopedUpdateView):
    model = FlightLog
    form_class = FlightLogForm


class FlightLogDeleteView(ScopedDeleteView):
    model = FlightLog

    def get_source_url(self):
        return reverse("ops:workspace", args=[self.object.program_id])
