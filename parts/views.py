"""参考数据的四个列表页（列表 + 弹窗增删改，文档 11 / 12）。

引擎 / 燃料罐 / 科学设备跨存档共用，用弹窗就地增删改（POST 回各自列表页）；
天体由 fixture 提供，只读。**每类数据独立成页**，二级导航在 `templates/parts/reference_base.html`。
"""

from django.urls import reverse
from django.views.generic import ListView, RedirectView

from core.models import Body
from core.views import CrudListView

from .forms import EngineForm, FuelTankForm, ScienceInstrumentForm
from .models import Engine, FuelTank, ScienceInstrument


class ReferenceRedirectView(RedirectView):
    """旧的 `/reference/` → 引擎列表（302，只为了让旧书签不 404，文档 11 第 2.1 节）。"""

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse("parts:engine_list")


class EngineListView(CrudListView):
    model = Engine
    form_class = EngineForm
    template_name = "parts/engine_list.html"
    context_object_name = "engines"


class FuelTankListView(CrudListView):
    model = FuelTank
    form_class = FuelTankForm
    template_name = "parts/fueltank_list.html"
    context_object_name = "fuel_tanks"


class ScienceInstrumentListView(CrudListView):
    model = ScienceInstrument
    form_class = ScienceInstrumentForm
    template_name = "parts/instrument_list.html"
    context_object_name = "instruments"


class BodyListView(ListView):
    """天体页：由 fixture 提供，**只读**（没有新增/编辑/删除）。"""

    model = Body
    template_name = "parts/body_list.html"
    context_object_name = "bodies"
