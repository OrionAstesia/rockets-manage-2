from django.urls import path

from .views import ScheduleView

app_name = "ops"

urlpatterns = [
    path("schedule/", ScheduleView.as_view(), name="schedule"),
]
