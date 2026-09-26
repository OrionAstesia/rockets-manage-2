"""火箭、载荷与级的表单（改造文档 10 第 4.5 / 5.5 节）。

火箭与载荷有必填的 `program`（所属存档），由视图从 URL/实例注入，表单里不出现；
级挂在火箭上，`rocket` 同样从 URL 注入。
"""

from core.forms import BaseModelForm, ProgramScopedFormMixin

from .models import Payload, Rocket, RocketStage


class RocketForm(ProgramScopedFormMixin, BaseModelForm):
    class Meta:
        model = Rocket
        fields = [
            "name", "series", "manufacturer", "diameter",
            "first_flight_date", "crew_capacity", "cost", "is_reusable", "note",
        ]


class PayloadForm(ProgramScopedFormMixin, BaseModelForm):
    class Meta:
        model = Payload
        fields = [
            "name", "payload_type", "mass", "diameter",
            "crew_capacity", "has_docking_port", "cost", "note",
        ]


class StageForm(BaseModelForm):
    """级表单：`rocket` 从 URL `?rocket=<pk>` 注入，序号自动建议下一个。"""

    class Meta:
        model = RocketStage
        fields = [
            "stage_order", "engine", "engine_count", "fuel_tank", "tank_count",
            "structure_mass", "separation_type", "note",
        ]
        help_texts = {
            "stage_order": "1 = 最先点火、最下面那一级（起飞级），向上递增。"
                           "页面自上而下显示时最上级在顶部。",
        }

    def __init__(self, *args, rocket=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("rocket", None)               # 不显示、也不接受用户提交
        if rocket is not None:
            self.instance.rocket = rocket
        # getattr 是安全的：实例上没设 rocket 时访问它抛 RelatedObjectDoesNotExist（继承 AttributeError）
        self.rocket = rocket or getattr(self.instance, "rocket", None)
        if rocket is not None and not self.is_bound and not self.instance.pk:
            last = rocket.stages.order_by("-stage_order").first()
            self.initial["stage_order"] = (last.stage_order + 1) if last else 1

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("stage_order")
        if order is not None and self.rocket is not None:
            # DB 有 UniqueConstraint(["rocket", "stage_order"])，但 rocket 不在表单字段里，
            # ModelForm 的 validate_constraints 会跳过这条约束 —— 不自己查就是 IntegrityError(500)
            same = RocketStage.objects.filter(rocket=self.rocket, stage_order=order)
            if self.instance.pk:
                same = same.exclude(pk=self.instance.pk)
            if same.exists():
                self.add_error("stage_order", f"这枚火箭已经有第 {order} 级了，请换一个级序号。")
        return cleaned
