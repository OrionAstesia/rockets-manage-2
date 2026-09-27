from django.urls import path

from .views import RocketDetailView

app_name = "fleet"

urlpatterns = [
    # 火箭详情页同时承担「级的弹窗增删改」：GET 看级序与 Δv，POST 按 action 分流
    path("rockets/<int:pk>/", RocketDetailView.as_view(), name="rocket_detail"),
]
