"""火箭详情（含级的弹窗增删改）与火箭/载荷/级的旧 CRUD 视图。

新增：火箭详情页上的**级**改为弹窗增删改，POST 回详情页自己的 URL（文档 12 第 5.3 节）。
下方那些 `*CreateView` / `*UpdateView` / `*DeleteView` 是文档 12 之前的独立表单页/确认页，
在路由删除（同一次改造的最后一步）之后会一起移除。
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from core.views import (
    DialogCrudMixin,
    FormPageMixin,
    SafeDeleteMixin,
    ScopedCreateView,
    ScopedDeleteView,
    ScopedUpdateView,
)
from services.orbital import vehicle_delta_v

from .forms import PayloadForm, RocketForm, StageForm
from .models import Payload, Rocket, RocketStage


class RocketDetailView(DialogCrudMixin, DetailView):
    """火箭详情：级序列表（降序渲染）+ 逐级 Δv + 总 Δv，以及**级的弹窗增删改**。

    级的归属校验按 `rocket=self.object`（不是 `program`）。
    """

    model = Rocket
    template_name = "fleet/rocket_detail.html"

    # ---- 弹窗增删改的两个钩子（操作对象是「级」） ----
    def get_scoped_object(self, pk):
        if not (pk and str(pk).isdigit()):
            return None
        return self.object.stages.filter(pk=pk).first()

    def build_form(self, data, instance, prefix=None):
        return StageForm(data, instance=instance, rocket=self.object, prefix=prefix)

    def get_rows(self):
        return []          # 本页不用通用 rows 循环，表格行在 get_context_data 里自己拼

    # ---- POST 前先取到火箭 ----
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stage_rows"] = vehicle_delta_v(self.object)          # 已按 stage_order 升序
        ctx["total_dv"] = sum(r["delta_v"] or 0 for r in ctx["stage_rows"])
        # 页面上一行同时显示「级配置」「Δv」与两个弹窗按钮，所以把级对象与它的表单挂到对应行上。
        # 两个序列同序（都按 stage_order 升序），zip 是安全的。
        stages = list(
            self.object.stages.select_related("engine", "fuel_tank").order_by("stage_order")
        )
        for row, stage in zip(ctx["stage_rows"], stages):
            row["stage"] = stage
            row["form"] = self.build_form(None, stage, prefix=f"e{stage.pk}")
            row["prefix"] = f"e{stage.pk}"
            row["edit_id"] = f"dlg-edit-{stage.pk}"
            row["del_id"] = f"dlg-del-{stage.pk}"
        # 校验失败时把带错误的表单挂回那一行，并让该弹窗自动打开
        for row in ctx["stage_rows"]:
            row["open_edit"] = self.open_dialog == "edit" and self.open_pk == row["stage"].pk
            if row["open_edit"] and self.bound_form is not None:
                row["form"] = self.bound_form
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
