from django.urls import path

from .views import (
    FlightLogCreateView,
    FlightLogDeleteView,
    FlightLogUpdateView,
    SaveFlightsView,
    SavePayloadsView,
    SaveRocketsView,
    SaveSitesView,
    SaveSpacecraftView,
    ScheduleView,
    WorkspaceView,
)

app_name = "ops"

urlpatterns = [
    # 存档下的五个集合（二级导航的目标；必须排在 saves/<int:pk>/ 之前，保持匹配直觉）
    path("saves/<int:pk>/rockets/", SaveRocketsView.as_view(), name="save_rockets"),
    path("saves/<int:pk>/payloads/", SavePayloadsView.as_view(), name="save_payloads"),
    path("saves/<int:pk>/sites/", SaveSitesView.as_view(), name="save_sites"),
    path("saves/<int:pk>/spacecraft/", SaveSpacecraftView.as_view(), name="save_spacecraft"),
    path("saves/<int:pk>/flights/", SaveFlightsView.as_view(), name="save_flights"),
    # 旧入口（下一步改成 302 到火箭列表；本步先保留工作台，测试仍绿）
    path("saves/<int:pk>/", WorkspaceView.as_view(), name="workspace"),
    path("schedule/", ScheduleView.as_view(), name="schedule"),
    path("flights/new/", FlightLogCreateView.as_view(), name="flight_create"),
    path("flights/<int:pk>/edit/", FlightLogUpdateView.as_view(), name="flight_update"),
    path("flights/<int:pk>/delete/", FlightLogDeleteView.as_view(), name="flight_delete"),
]
