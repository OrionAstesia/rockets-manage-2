"""参考数据页与部件的增删改（改造文档 10 第 4.4 节）。

引擎 / 燃料罐 / 科学设备跨存档共用，前台可就地增删改；天体由 fixture 提供，只读。
"""

from django.contrib import messages
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from core.models import Body
from core.views import FormPageMixin, SafeDeleteMixin

from .forms import EngineForm, FuelTankForm, ScienceInstrumentForm
from .models import Engine, FuelTank, ScienceInstrument


class ReferenceView(TemplateView):
    """`/reference/`：3 个可编辑区块 + 只读的天体区块。"""

    template_name = "parts/reference.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bodies"] = Body.objects.all()
        ctx["engines"] = Engine.objects.all()
        ctx["fuel_tanks"] = FuelTank.objects.all()
        ctx["instruments"] = ScienceInstrument.objects.all()
        return ctx


class ReferenceFormMixin(FormPageMixin):
    """参考数据的「取消」与保存后都回到 `/reference/`。"""

    def get_source_url(self):
        return reverse("parts:reference")

    def get_success_url(self):
        messages.success(self.request, "已保存。")
        return self.get_source_url()


class EngineCreateView(ReferenceFormMixin, CreateView):
    model = Engine
    form_class = EngineForm


class EngineUpdateView(ReferenceFormMixin, UpdateView):
    model = Engine
    form_class = EngineForm


class EngineDeleteView(SafeDeleteMixin, DeleteView):
    model = Engine

    def get_source_url(self):
        return reverse("parts:reference")


class FuelTankCreateView(ReferenceFormMixin, CreateView):
    model = FuelTank
    form_class = FuelTankForm


class FuelTankUpdateView(ReferenceFormMixin, UpdateView):
    model = FuelTank
    form_class = FuelTankForm


class FuelTankDeleteView(SafeDeleteMixin, DeleteView):
    model = FuelTank

    def get_source_url(self):
        return reverse("parts:reference")


class ScienceInstrumentCreateView(ReferenceFormMixin, CreateView):
    model = ScienceInstrument
    form_class = ScienceInstrumentForm


class ScienceInstrumentUpdateView(ReferenceFormMixin, UpdateView):
    model = ScienceInstrument
    form_class = ScienceInstrumentForm


class ScienceInstrumentDeleteView(SafeDeleteMixin, DeleteView):
    model = ScienceInstrument

    def get_source_url(self):
        return reverse("parts:reference")
