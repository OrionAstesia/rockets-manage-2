"""URL 汇总（文档 11 §2 / 12 §2）。

前台只剩这些「读」入口；增删改没有独立路由，全部是各列表页上的弹窗（POST 回同一条 URL）：

| URL | 说明 |
|---|---|
| `/` | 主页（暂空） |
| `/saves/` | 存档列表 + 存档弹窗增删改 |
| `/saves/<pk>/{rockets,payloads,sites,spacecraft,flights}/` | 存档下五个集合，各带弹窗增删改 |
| `/rockets/<pk>/` | 火箭详情 + 级的弹窗增删改 |
| `/reference/{engines,fueltanks,instruments,bodies}/` | 参考数据（天体只读） |
| `/schedule/` | 发射日程 |

`spaceflight` 已没有自己的 URL：发射场/航天器分别在 `/saves/<pk>/sites/` 与
`/saves/<pk>/spacecraft/` 上维护（所以这个 app 的 urls.py / views.py 已删除）。
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
]
