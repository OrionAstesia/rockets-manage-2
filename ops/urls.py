from django.urls import path

from .views import (
    FlightLogCreateView,
    FlightLogDeleteView,
    FlightLogUpdateView,
    ScheduleView,
    WorkspaceView,
)

app_name = "ops"

urlpatterns = [
    path("saves/<int:pk>/", WorkspaceView.as_view(), name="workspace"),
    path("schedule/", ScheduleView.as_view(), name="schedule"),
    path("flights/new/", FlightLogCreateView.as_view(), name="flight_create"),
    path("flights/<int:pk>/edit/", FlightLogUpdateView.as_view(), name="flight_update"),
    path("flights/<int:pk>/delete/", FlightLogDeleteView.as_view(), name="flight_delete"),
]
