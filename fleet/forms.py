"""火箭与载荷表单（改造文档 10 第 4.5 节）。

两者都有必填的 `program`（所属存档），由视图从 URL/实例注入，表单里不出现。
"""

from core.forms import BaseModelForm, ProgramScopedFormMixin

from .models import Payload, Rocket


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
