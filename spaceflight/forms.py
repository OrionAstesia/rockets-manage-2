"""发射场与在轨航天器表单（改造文档 10 第 4.5 节）。

两者的 `body`（所在天体）是跨存档的参考数据，不限制；`Spacecraft.source_flight`
限制在本存档的发射日志内。
"""

from core.forms import BaseModelForm, ProgramScopedFormMixin

from .models import Site, Spacecraft


class SiteForm(ProgramScopedFormMixin, BaseModelForm):
    class Meta:
        model = Site
        fields = [
            "name", "body", "latitude", "longitude",
            "max_mass", "is_operational", "note",
        ]


class SpacecraftForm(ProgramScopedFormMixin, BaseModelForm):
    class Meta:
        model = Spacecraft
        fields = [
            "name", "craft_type", "body", "situation", "is_active", "crew_count",
            "sma", "eccentricity", "inclination", "cached_period_sec",
            "source_flight", "note",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        program = self.program
        if program is not None:
            self.fields["source_flight"].queryset = program.flights.all()
