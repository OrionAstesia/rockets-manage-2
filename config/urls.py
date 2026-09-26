"""URL 汇总（改造文档 10 第 2 节）。

前台页面：`/`（存档列表）、`/saves/<pk>/`（工作台）、`/reference/`（参考数据）、
`/schedule/`（发射日程）、`/rockets/<pk>/`（火箭详情），以及各类
`/xxx/new/`、`/xxx/<pk>/edit/`、`/xxx/<pk>/delete/`。
`/admin/` 保留可用，只是前台不放入口。
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("ops.urls")),
    path("", include("fleet.urls")),
    path("", include("parts.urls")),
    path("", include("spaceflight.urls")),
]
