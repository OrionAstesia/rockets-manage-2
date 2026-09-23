from django.urls import path

from .views import RocketDetailView

app_name = "fleet"

urlpatterns = [
    path("rockets/<int:pk>/", RocketDetailView.as_view(), name="rocket_detail"),
]
