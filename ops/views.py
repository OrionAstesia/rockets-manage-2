"""发射日程（规格 §8.2）：只显示 state=PLANNED 的任务，按计划日期升序。"""

from django.db.models import F
from django.views.generic import ListView

from .models import FlightLog, FlightState


class ScheduleView(ListView):
    model = FlightLog
    template_name = "ops/schedule.html"
    context_object_name = "flights"

    def get_queryset(self):
        return (
            FlightLog.objects.filter(state=FlightState.PLANNED)
            .select_related("rocket", "payload", "site")
            # 计划日期为空的（「未定」）排在最后，与首页「近期发射」的处理一致
            .order_by(F("planned_date").asc(nulls_last=True))
        )
