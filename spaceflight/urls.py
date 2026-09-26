from django.urls import path

from .views import (
    SiteCreateView,
    SiteDeleteView,
    SiteUpdateView,
    SpacecraftCreateView,
    SpacecraftDeleteView,
    SpacecraftUpdateView,
)

app_name = "spaceflight"

urlpatterns = [
    path("sites/new/", SiteCreateView.as_view(), name="site_create"),
    path("sites/<int:pk>/edit/", SiteUpdateView.as_view(), name="site_update"),
    path("sites/<int:pk>/delete/", SiteDeleteView.as_view(), name="site_delete"),
    path("spacecraft/new/", SpacecraftCreateView.as_view(), name="spacecraft_create"),
    path("spacecraft/<int:pk>/edit/", SpacecraftUpdateView.as_view(), name="spacecraft_update"),
    path("spacecraft/<int:pk>/delete/", SpacecraftDeleteView.as_view(), name="spacecraft_delete"),
]
