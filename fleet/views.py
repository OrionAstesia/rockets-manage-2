"""火箭详情与火箭/载荷/级的增删改（改造文档 10 第 4.3 / 5.5 节）。"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from core.views import (
    FormPageMixin,
    SafeDeleteMixin,
    ScopedCreateView,
    ScopedDeleteView,
    ScopedUpdateView,
)
from services.orbital import vehicle_delta_v

from .forms import PayloadForm, RocketForm, StageForm
from .models import Payload, Rocket, RocketStage


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
    list_url_name = "ops:save_rockets"


class RocketUpdateView(ScopedUpdateView):
    model = Rocket
    form_class = RocketForm

    def get_source_url(self):
        # 有意的例外：改完火箭回它的详情页（要看级与 Δv），不回列表
        return reverse("fleet:rocket_detail", args=[self.object.pk])


class RocketDeleteView(ScopedDeleteView):
    model = Rocket
    list_url_name = "ops:save_rockets"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["extra_warning"] = f"这枚火箭的 {self.object.stages.count()} 级将一并删除。"
        return ctx


class PayloadCreateView(ScopedCreateView):
    model = Payload
    form_class = PayloadForm
    list_url_name = "ops:save_payloads"


class PayloadUpdateView(ScopedUpdateView):
    model = Payload
    form_class = PayloadForm
    list_url_name = "ops:save_payloads"


class PayloadDeleteView(ScopedDeleteView):
    model = Payload
    list_url_name = "ops:save_payloads"


class StageCreateView(FormPageMixin, CreateView):
    """`/stages/new/?rocket=<pk>`：级单独成页，不嵌在火箭页里。"""

    model = RocketStage
    form_class = StageForm

    def dispatch(self, request, *args, **kwargs):
        rocket_id = request.GET.get("rocket", "")
        self.rocket = Rocket.objects.filter(pk=rocket_id).first() if rocket_id.isdigit() else None
        if self.rocket is None:
            messages.error(request, "请先从火箭详情页点「+ 新增一级」。")
            return redirect("core:save_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "rocket": self.rocket}

    def get_source_url(self):
        return reverse("fleet:rocket_detail", args=[self.rocket.pk])

    def form_title(self):
        return f"新增级：{self.rocket.name}"

    def get_success_url(self):
        messages.success(self.request, f"已新增：{self.object}")
        return self.get_source_url()


class StageUpdateView(FormPageMixin, UpdateView):
    model = RocketStage
    form_class = StageForm

    def get_source_url(self):
        return reverse("fleet:rocket_detail", args=[self.object.rocket_id])

    def form_title(self):
        return f"编辑级：{self.object}"

    def get_success_url(self):
        messages.success(self.request, "已保存。")
        return self.get_source_url()


class StageDeleteView(SafeDeleteMixin, DeleteView):
    model = RocketStage

    def get_source_url(self):
        return reverse("fleet:rocket_detail", args=[self.object.rocket_id])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["extra_warning"] = "删除这一级之后，它的 Δv 会从总 Δv 里消失。"
        return ctx
