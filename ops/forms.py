"""发射日志表单（改造文档 10 第 4.5 节）。

`rocket` / `payload` / `site` 三个外键的下拉**限制在本存档内**，避免把别的存档的
火箭或发射场挂到这条任务上。
"""

from core.forms import BaseModelForm, ProgramScopedFormMixin

from .models import FlightLog


class FlightLogForm(ProgramScopedFormMixin, BaseModelForm):
    class Meta:
        model = FlightLog
        fields = [
            "name", "state", "planned_date", "actual_date",
            "rocket", "payload", "site",
            "crew_count", "result_code", "rest_dv", "cost", "detail",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        program = self.program
        if program is not None:
            self.fields["rocket"].queryset = program.rockets.all()
            self.fields["payload"].queryset = program.payloads.all()
            self.fields["site"].queryset = program.sites.all()
