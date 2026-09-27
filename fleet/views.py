"""火箭详情页：级序列表 + Δv，以及**级的弹窗增删改**（文档 11 §4.3 / 12 §5.3）。

火箭与载荷本身的增删改在各自存档的列表页上用弹窗完成（`ops:save_rockets` / `ops:save_payloads`），
所以本文件只有这一个视图。
"""

from django.views.generic import DetailView

from core.views import DialogCrudMixin
from services.orbital import vehicle_delta_v

from .forms import StageForm
from .models import Rocket


class RocketDetailView(DialogCrudMixin, DetailView):
    """级的归属校验按 `rocket=self.object`（不是 `program`）。"""

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
