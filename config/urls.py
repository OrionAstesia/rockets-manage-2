"""URL 汇总（规格 §8.2）。

前台只有 3 个只读页面：`/`、`/schedule/`、`/rockets/<pk>/`；所有写操作走 `/admin/`。
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("ops.urls")),
    path("", include("fleet.urls")),
]
