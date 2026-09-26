"""部件（参考数据）表单（改造文档 10 第 4.4 节）。

引擎 / 燃料罐 / 科学设备是跨存档共用的参考数据，**没有** `program` 外键。
"""

from core.forms import BaseModelForm

from .models import Engine, FuelTank, ScienceInstrument


class EngineForm(BaseModelForm):
    class Meta:
        model = Engine
        fields = [
            "name", "diameter", "dry_mass",
            "thrust_asl", "thrust_vac", "isp_asl", "isp_vac", "cost",
        ]


class FuelTankForm(BaseModelForm):
    class Meta:
        model = FuelTank
        fields = ["name", "diameter", "dry_mass", "capacity", "fuel_type", "cost"]


class ScienceInstrumentForm(BaseModelForm):
    class Meta:
        model = ScienceInstrument
        fields = [
            "name", "dry_mass", "experiment_type", "data_value",
            "is_repeatable", "requires_crew", "cost",
        ]
