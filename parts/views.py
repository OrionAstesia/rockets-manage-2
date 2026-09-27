"""参考数据的四个列表页与部件的弹窗增删改（文档 11 / 12）。

引擎 / 燃料罐 / 科学设备跨存档共用，前台用弹窗就地增删改（POST 回各自列表页）；
天体由 fixture 提供，只读。**每类数据独立成页**，二级导航在 `templates/parts/reference_base.html` 里。
"""

from django.contrib import messages
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, RedirectView, UpdateView

from core.models import Body
from core.views import CrudListView, FormPageMixin, SafeDeleteMixin

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
    """天体页：由 fixture 提供，**只读**（无新增/编辑/删除）。"""

    model = Body
    template_name = "parts/body_list.html"
    context_object_name = "bodies"


class ReferenceFormMixin(FormPageMixin):
    """参考数据的新增/编辑：保存与取消都回到该部件自己的列表页。"""

    list_url_name = ""

    def get_source_url(self):
        return reverse(self.list_url_name)

    def get_success_url(self):
        messages.success(self.request, "已保存。")
        return self.get_source_url()


class EngineCreateView(ReferenceFormMixin, CreateView):
    model = Engine
    form_class = EngineForm
    list_url_name = "parts:engine_list"


class EngineUpdateView(ReferenceFormMixin, UpdateView):
    model = Engine
    form_class = EngineForm
    list_url_name = "parts:engine_list"


class EngineDeleteView(SafeDeleteMixin, DeleteView):
    model = Engine

    def get_source_url(self):
        return reverse("parts:engine_list")


class FuelTankCreateView(ReferenceFormMixin, CreateView):
    model = FuelTank
    form_class = FuelTankForm
    list_url_name = "parts:fueltank_list"


class FuelTankUpdateView(ReferenceFormMixin, UpdateView):
    model = FuelTank
    form_class = FuelTankForm
    list_url_name = "parts:fueltank_list"


class FuelTankDeleteView(SafeDeleteMixin, DeleteView):
    model = FuelTank

    def get_source_url(self):
        return reverse("parts:fueltank_list")


class ScienceInstrumentCreateView(ReferenceFormMixin, CreateView):
    model = ScienceInstrument
    form_class = ScienceInstrumentForm
    list_url_name = "parts:instrument_list"


class ScienceInstrumentUpdateView(ReferenceFormMixin, UpdateView):
    model = ScienceInstrument
    form_class = ScienceInstrumentForm
    list_url_name = "parts:instrument_list"


class ScienceInstrumentDeleteView(SafeDeleteMixin, DeleteView):
    model = ScienceInstrument

    def get_source_url(self):
        return reverse("parts:instrument_list")
