from django.urls import path

from .views import (
    EngineCreateView,
    EngineDeleteView,
    EngineUpdateView,
    FuelTankCreateView,
    FuelTankDeleteView,
    FuelTankUpdateView,
    ReferenceView,
    ScienceInstrumentCreateView,
    ScienceInstrumentDeleteView,
    ScienceInstrumentUpdateView,
)

app_name = "parts"

urlpatterns = [
    path("reference/", ReferenceView.as_view(), name="reference"),
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
