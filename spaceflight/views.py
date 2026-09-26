"""发射场与在轨航天器的增删改（改造文档 10 第 4.2 / 4.5 节）。"""

from core.views import ScopedCreateView, ScopedDeleteView, ScopedUpdateView

from .forms import SiteForm, SpacecraftForm
from .models import Site, Spacecraft


class SiteCreateView(ScopedCreateView):
    model = Site
    form_class = SiteForm


class SiteUpdateView(ScopedUpdateView):
    model = Site
    form_class = SiteForm


class SiteDeleteView(ScopedDeleteView):
    model = Site


class SpacecraftCreateView(ScopedCreateView):
    model = Spacecraft
    form_class = SpacecraftForm


class SpacecraftUpdateView(ScopedUpdateView):
    model = Spacecraft
    form_class = SpacecraftForm


class SpacecraftDeleteView(ScopedDeleteView):
    model = Spacecraft
