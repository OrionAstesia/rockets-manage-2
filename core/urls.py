from django.urls import path

from .views import HomeView, SaveCreateView, SaveDeleteView, SaveListView, SaveUpdateView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),                   # 主页（暂空）
    path("saves/", SaveListView.as_view(), name="save_list"),     # 存档列表（原在 /）
    path("saves/new/", SaveCreateView.as_view(), name="save_create"),
    path("saves/<int:pk>/edit/", SaveUpdateView.as_view(), name="save_update"),
    path("saves/<int:pk>/delete/", SaveDeleteView.as_view(), name="save_delete"),
]
