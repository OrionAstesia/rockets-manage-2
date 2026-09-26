from django.urls import path

from .views import (
    BodyListView,
    EngineCreateView,
    EngineDeleteView,
    EngineListView,
    EngineUpdateView,
    FuelTankCreateView,
    FuelTankDeleteView,
    FuelTankListView,
    FuelTankUpdateView,
    ReferenceRedirectView,
    ScienceInstrumentCreateView,
    ScienceInstrumentDeleteView,
    ScienceInstrumentListView,
    ScienceInstrumentUpdateView,
)

app_name = "parts"

urlpatterns = [
    # 旧入口 → 302 到引擎列表
    path("reference/", ReferenceRedirectView.as_view(), name="reference"),
    # 参考数据的四个列表页（二级导航的目标；顺序＝导航顺序：引擎/燃料罐/科学设备/天体）
    path("reference/engines/", EngineListView.as_view(), name="engine_list"),
    path("reference/fueltanks/", FuelTankListView.as_view(), name="fueltank_list"),
    path("reference/instruments/", ScienceInstrumentListView.as_view(), name="instrument_list"),
    path("reference/bodies/", BodyListView.as_view(), name="body_list"),
    # 以下 URL 不动，只改保存/取消之后回到哪张列表（见 views 里的 list_url_name）
    path("engines/new/", EngineCreateView.as_view(), name="engine_create"),
    path("engines/<int:pk>/edit/", EngineUpdateView.as_view(), name="engine_update"),
    path("engines/<int:pk>/delete/", EngineDeleteView.as_view(), name="engine_delete"),
    path("fueltanks/new/", FuelTankCreateView.as_view(), name="fueltank_create"),
    path("fueltanks/<int:pk>/edit/", FuelTankUpdateView.as_view(), name="fueltank_update"),
    path("fueltanks/<int:pk>/delete/", FuelTankDeleteView.as_view(), name="fueltank_delete"),
    path("instruments/new/", ScienceInstrumentCreateView.as_view(), name="instrument_create"),
    path("instruments/<int:pk>/edit/", ScienceInstrumentUpdateView.as_view(), name="instrument_update"),
    path("instruments/<int:pk>/delete/", ScienceInstrumentDeleteView.as_view(), name="instrument_delete"),
]
