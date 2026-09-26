from django.urls import path

from .views import HomeView, SaveCreateView, SaveDeleteView, SaveUpdateView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("saves/new/", SaveCreateView.as_view(), name="save_create"),
    path("saves/<int:pk>/edit/", SaveUpdateView.as_view(), name="save_update"),
    path("saves/<int:pk>/delete/", SaveDeleteView.as_view(), name="save_delete"),
]
