"""URL 汇总（规格 §8.2）。

前台只有 3 个只读页面：`/`（S4）、`/schedule/`（S4）、`/rockets/<pk>/`（S3，本步已加）。
所有写操作走 `/admin/`。
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("fleet.urls")),
]
