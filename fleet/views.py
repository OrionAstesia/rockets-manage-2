"""火箭详情与火箭/载荷的增删改（改造文档 10 第 4.3 节）。"""

from django.urls import reverse
from django.views.generic import DetailView

from core.views import ScopedCreateView, ScopedDeleteView, ScopedUpdateView
from services.orbital import vehicle_delta_v

from .forms import PayloadForm, RocketForm
from .models import Payload, Rocket


class RocketDetailView(DetailView):
    """火箭详情：级序列表（降序渲染）+ 逐级 Δv + 总 Δv。"""

    model = Rocket
    template_name = "fleet/rocket_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stage_rows"] = vehicle_delta_v(self.object)          # 已按 stage_order 升序
        ctx["total_dv"] = sum(r["delta_v"] or 0 for r in ctx["stage_rows"])
        # 页面上一行同时显示「级配置」与「Δv」，所以把级对象挂到对应的 Δv 行上。
        # 两个序列同序（都按 stage_order 升序），zip 是安全的。
        stages = list(
            self.object.stages.select_related("engine", "fuel_tank").order_by("stage_order")
        )
        for row, stage in zip(ctx["stage_rows"], stages):
            row["stage"] = stage
        return ctx


class RocketCreateView(ScopedCreateView):
    model = Rocket
    form_class = RocketForm


class RocketUpdateView(ScopedUpdateView):
    model = Rocket
    form_class = RocketForm

    def get_source_url(self):
        return reverse("fleet:rocket_detail", args=[self.object.pk])


class RocketDeleteView(ScopedDeleteView):
    model = Rocket

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["extra_warning"] = f"这枚火箭的 {self.object.stages.count()} 级将一并删除。"
        return ctx


class PayloadCreateView(ScopedCreateView):
    model = Payload
    form_class = PayloadForm


class PayloadUpdateView(ScopedUpdateView):
    model = Payload
    form_class = PayloadForm


class PayloadDeleteView(ScopedDeleteView):
    model = Payload
