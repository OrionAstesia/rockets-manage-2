"""发射场与在轨航天器的增删改（改造文档 10 第 4.2 / 4.5 节）。

`list_url_name` 决定保存/取消/删除之后回到哪张列表（文档 11 §6.1，现在每类数据独立成页）。
"""

from core.views import ScopedCreateView, ScopedDeleteView, ScopedUpdateView

from .forms import SiteForm, SpacecraftForm
from .models import Site, Spacecraft


class SiteCreateView(ScopedCreateView):
    model = Site
    form_class = SiteForm
    list_url_name = "ops:save_sites"


class SiteUpdateView(ScopedUpdateView):
    model = Site
    form_class = SiteForm
    list_url_name = "ops:save_sites"


class SiteDeleteView(ScopedDeleteView):
    model = Site
    list_url_name = "ops:save_sites"


class SpacecraftCreateView(ScopedCreateView):
    model = Spacecraft
    form_class = SpacecraftForm
    list_url_name = "ops:save_spacecraft"


class SpacecraftUpdateView(ScopedUpdateView):
    model = Spacecraft
    form_class = SpacecraftForm
    list_url_name = "ops:save_spacecraft"


class SpacecraftDeleteView(ScopedDeleteView):
    model = Spacecraft
    list_url_name = "ops:save_spacecraft"
