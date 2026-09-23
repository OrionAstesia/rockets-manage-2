from django.views.generic import DetailView

from services.orbital import vehicle_delta_v

from .models import Rocket


class RocketDetailView(DetailView):
    """火箭详情（规格 §8.2）：级序列表（降序渲染）+ 逐级 Δv + 总 Δv。"""

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
