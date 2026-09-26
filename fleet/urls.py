from django.urls import path

from .views import (
    PayloadCreateView,
    PayloadDeleteView,
    PayloadUpdateView,
    RocketCreateView,
    RocketDeleteView,
    RocketDetailView,
    RocketUpdateView,
    StageCreateView,
    StageDeleteView,
    StageUpdateView,
)

app_name = "fleet"

urlpatterns = [
    path("rockets/new/", RocketCreateView.as_view(), name="rocket_create"),
    path("rockets/<int:pk>/", RocketDetailView.as_view(), name="rocket_detail"),
    path("rockets/<int:pk>/edit/", RocketUpdateView.as_view(), name="rocket_update"),
    path("rockets/<int:pk>/delete/", RocketDeleteView.as_view(), name="rocket_delete"),
    path("payloads/new/", PayloadCreateView.as_view(), name="payload_create"),
    path("payloads/<int:pk>/edit/", PayloadUpdateView.as_view(), name="payload_update"),
    path("payloads/<int:pk>/delete/", PayloadDeleteView.as_view(), name="payload_delete"),
    path("stages/new/", StageCreateView.as_view(), name="stage_create"),
    path("stages/<int:pk>/edit/", StageUpdateView.as_view(), name="stage_update"),
    path("stages/<int:pk>/delete/", StageDeleteView.as_view(), name="stage_delete"),
]
