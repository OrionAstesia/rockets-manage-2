from django.urls import path

from .views import (
    SaveFlightsView,
    SavePayloadsView,
    SaveRocketsView,
    SaveSitesView,
    SaveSpacecraftView,
    ScheduleView,
)

app_name = "ops"

urlpatterns = [
    # 存档下的五个集合：GET 渲染列表，POST 在同一条 URL 上按 action 分流（文档 12）
    path("saves/<int:pk>/rockets/", SaveRocketsView.as_view(), name="save_rockets"),
    path("saves/<int:pk>/payloads/", SavePayloadsView.as_view(), name="save_payloads"),
    path("saves/<int:pk>/sites/", SaveSitesView.as_view(), name="save_sites"),
    path("saves/<int:pk>/spacecraft/", SaveSpacecraftView.as_view(), name="save_spacecraft"),
    path("saves/<int:pk>/flights/", SaveFlightsView.as_view(), name="save_flights"),
    path("schedule/", ScheduleView.as_view(), name="schedule"),
]
