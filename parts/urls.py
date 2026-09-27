from django.urls import path

from .views import (
    BodyListView,
    EngineListView,
    FuelTankListView,
    ReferenceRedirectView,
    ScienceInstrumentListView,
)

app_name = "parts"

urlpatterns = [
    # 旧入口 → 302 到引擎列表（让旧书签不 404）
    path("reference/", ReferenceRedirectView.as_view(), name="reference"),
    # 参考数据的四个列表页：GET 列表，POST 在同一条 URL 上按 action 分流（文档 12）
    path("reference/engines/", EngineListView.as_view(), name="engine_list"),
    path("reference/fueltanks/", FuelTankListView.as_view(), name="fueltank_list"),
    path("reference/instruments/", ScienceInstrumentListView.as_view(), name="instrument_list"),
    path("reference/bodies/", BodyListView.as_view(), name="body_list"),
]
