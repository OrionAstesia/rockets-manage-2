from django.urls import path

from .views import HomeView, SaveListView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),                   # 主页（暂空）
    path("saves/", SaveListView.as_view(), name="save_list"),     # 存档列表 + 弹窗增删改
]
