"""存档各集合的列表页（列表 + 弹窗增删改）与发射日程（文档 11 / 12）。

每个集合**独立成页**：一页只显示一张表，二级导航在 `templates/ops/save_base.html` 里。
增删改没有独立路由，全部 POST 回列表页自己的 URL，靠 `action` 字段分流（文档 12 第 4 节）。
"""

from django.db.models import Count, F
from django.views.generic import ListView

from core.views import SaveScopedCrudView
from fleet.forms import PayloadForm, RocketForm
from fleet.models import Payload, Rocket
from services.orbital import orbital_period
from spaceflight.forms import SiteForm, SpacecraftForm
from spaceflight.models import Site, Spacecraft

from .forms import FlightLogForm
from .models import FlightLog, FlightState


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


class SaveRocketsView(SaveScopedCrudView):
    model = Rocket
    form_class = RocketForm
    template_name = "ops/save_rockets.html"
    context_object_name = "rockets"
    select_related = ()

    def get_queryset(self):
        # 「级数」列：一次 annotate，避免每行再来一次 count 查询
        return super().get_queryset().annotate(stage_total=Count("stages"))


class SavePayloadsView(SaveScopedCrudView):
    model = Payload
    form_class = PayloadForm
    template_name = "ops/save_payloads.html"
    context_object_name = "payloads"


class SaveSitesView(SaveScopedCrudView):
    model = Site
    form_class = SiteForm
    template_name = "ops/save_sites.html"
    context_object_name = "sites"
    select_related = ("body",)


class SaveSpacecraftView(SaveScopedCrudView):
    model = Spacecraft
    form_class = SpacecraftForm
    template_name = "ops/save_spacecraft.html"
    context_object_name = "spacecraft"
    select_related = ("body",)

    def get_rows(self):
        rows = super().get_rows()
        for row in rows:
            row["period"] = period_text(row["obj"])     # 周期实时算，挂到行上给模板用
        return rows


class SaveFlightsView(SaveScopedCrudView):
    model = FlightLog
    form_class = FlightLogForm
    template_name = "ops/save_flights.html"
    context_object_name = "flights"
    select_related = ("rocket", "site")

    def get_rows(self):
        rows = super().get_rows()
        for row in rows:
            row["result"] = result_text(row["obj"])
        return rows


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
