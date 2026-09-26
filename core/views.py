"""前台视图（改造文档 10）。

除了首页/存档 CRUD，这里还放了四个**共用视图基类**，供 fleet / spaceflight / parts / ops
各自的新增-编辑-删除视图继承：

| 基类 | 用途 |
|---|---|
| `FormPageMixin` | 统一用 `templates/form.html` 渲染，并给出「取消」目标 |
| `ScopedCreateView` | `/xxx/new/?save=<pk>`：`program` 从 URL 取，表单里不出现 |
| `ScopedUpdateView` | `/xxx/<pk>/edit/`：`program` 取自实例 |
| `SafeDeleteMixin` / `ScopedDeleteView` | 仅 POST 的删除，捕获 `ProtectedError` |

⚠️ 外键属性名是 `program`，绝不能写成 `save`（`save` 会遮蔽 `Model.save()`）。
"""

from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from ops.models import FlightLog, Save
from spaceflight.models import CraftType, Spacecraft

from .forms import SaveForm

RECENT_FLIGHT_COUNT = 5


def protected_names(exc, limit=5):
    """把 `ProtectedError` 里的被保护实例拼成一小段可读文字。

    `exc.protected_objects` 是 **set**（不能切片，也没有固定顺序），所以先按字符串排序，
    保证同一份数据每次给出同样的提示。
    """
    objs = sorted(exc.protected_objects, key=str)
    names = "、".join(str(obj) for obj in objs[:limit])
    more = " 等" if len(objs) > limit else ""
    return f"{names}{more}"


class FormPageMixin:
    """新增/编辑页共用 `templates/form.html`。"""

    template_name = "form.html"

    def get_source_url(self):
        """「取消」与保存成功之后回到的页面。子类必须实现。"""
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.get_source_url()
        ctx["form_title"] = self.form_title()
        return ctx

    def form_title(self):
        action = "编辑" if self.object is not None else "新增"
        return f"{action}{self.model._meta.verbose_name}"


class ScopedCreateView(FormPageMixin, CreateView):
    """`/xxx/new/?save=<pk>`：`program` 从 URL 查询参数取，**不从表单取**（防篡改）。"""

    def dispatch(self, request, *args, **kwargs):
        save_id = request.GET.get("save", "")
        self.program = Save.objects.filter(pk=save_id).first() if save_id.isdigit() else None
        if self.program is None:
            messages.error(request, "请先从「存档」里进入某个存档，再点「+ 新增」。")
            return redirect("core:save_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "program": self.program}

    def get_source_url(self):
        return reverse("ops:workspace", args=[self.program.pk])

    def get_success_url(self):
        messages.success(self.request, f"已新增：{self.object}")
        return self.get_source_url()


class ScopedUpdateView(FormPageMixin, UpdateView):
    """编辑属于某个存档的记录：`program` 取自实例，不从表单取。"""

    def get_source_url(self):
        return reverse("ops:workspace", args=[self.object.program_id])

    def get_success_url(self):
        messages.success(self.request, "已保存。")
        return self.get_source_url()


class SafeDeleteMixin:
    """仅 POST 的删除；被 PROTECT 外键拦下时转成友好提示，而不是 500。

    列表页行尾的「删除」是一个 POST 表单，但它**不带** `confirmed` 字段，
    因此只跳到确认页；只有确认页上那个带 `confirmed=yes` 的表单才真的删。
    这样既满足「删除必须 POST」，又不会一点就删。
    """

    template_name = "confirm_delete.html"

    def get_source_url(self):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.get_source_url()
        ctx["delete_title"] = f"删除{self.model._meta.verbose_name}：{self.object}"
        return ctx

    def get_success_url(self):
        # DeleteView 先取 success_url 再删对象，所以这里读外键 id 是安全的
        return self.get_source_url()

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirmed") != "yes":
            self.object = self.get_object()
            return self.render_to_response(self.get_context_data())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        source_url = self.get_source_url()
        try:
            response = super().form_valid(form)
        except ProtectedError as exc:
            messages.error(
                self.request,
                f"删除失败：仍有数据引用它（{protected_names(exc)}），请先处理这些数据。",
            )
            return redirect(source_url)
        messages.success(self.request, "已删除。")
        return response


class ScopedDeleteView(SafeDeleteMixin, DeleteView):
    """删除属于某个存档的记录，删完回到该存档的工作台。"""

    def get_source_url(self):
        return reverse("ops:workspace", args=[self.object.program_id])


class HomeView(TemplateView):
    """主页 `/`：**暂空**，等后续开发补充（文档 11 第 2.1 节）。

    不要顺手把统计 / 近期发射之类的块搬进来 —— 那些块留在存档列表 `/saves/` 里，
    主页放什么等后续设计。
    """

    template_name = "core/home.html"


class SaveListView(TemplateView):
    """存档列表 `/saves/`：行内新建存档表单 + 存档表 + 全局统计 + 近期发射。

    内容原来在 `/` 上（文档 11 第 4.3 节要求把存档列表搬到 `/saves/`）。
    """

    template_name = "core/save_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["save_rows"] = Save.objects.annotate(
            rocket_total=Count("rockets", distinct=True),
            flight_total=Count("flights", distinct=True),
        )
        ctx["save_form"] = SaveForm()
        ctx["spacecraft_counts"] = self.spacecraft_counts()
        # 按计划日期降序；planned_date 为空的排在最后（SQLite 下 NULL 最小，DESC 自然靠后）
        ctx["recent_flights"] = (
            FlightLog.objects.select_related("rocket", "site")
            .order_by("-planned_date")[:RECENT_FLIGHT_COUNT]
        )
        return ctx

    @staticmethod
    def spacecraft_counts():
        """在役航天器按 craft_type 分组计数，如「空间站 2 · 中继卫星 3 · 探测器 1」。"""
        labels = dict(CraftType.choices)
        rows = (
            Spacecraft.objects.filter(is_active=True)
            .values("craft_type")
            .annotate(total=Count("id"))
            .order_by("-total", "craft_type")
        )
        counts = [
            {"label": labels.get(row["craft_type"], row["craft_type"]), "total": row["total"]}
            for row in rows
        ]
        return {"rows": counts, "total": sum(row["total"] for row in counts)}


class SaveCreateView(FormPageMixin, CreateView):
    """新建存档。存档列表 `/saves/` 上的行内表单也 POST 到这里。"""

    model = Save
    form_class = SaveForm

    def get_source_url(self):
        return reverse("core:save_list")

    def get_success_url(self):
        messages.success(self.request, f"已新增存档：{self.object}")
        return self.get_source_url()


class SaveUpdateView(FormPageMixin, UpdateView):
    """编辑存档。"""

    model = Save
    form_class = SaveForm

    def get_source_url(self):
        return reverse("core:save_list")

    def get_success_url(self):
        messages.success(self.request, "已保存。")
        return self.get_source_url()


class SaveDeleteView(SafeDeleteMixin, DeleteView):
    """删除存档：确认页必须列出将连带删除的各项数量（文档 10 第 4.1 节）。"""

    model = Save

    def get_source_url(self):
        return reverse("core:save_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        save = self.object
        ctx["related_counts"] = [
            ("火箭", save.rockets.count()),
            ("载荷", save.payloads.count()),
            ("发射场", save.sites.count()),
            ("航天器", save.spacecraft.count()),
            ("发射日志", save.flights.count()),
        ]
        ctx["extra_warning"] = "删除存档 = 清空它里面的火箭、载荷、发射场、航天器、发射日志。"
        return ctx

    def form_valid(self, form):
        save = self.object
        try:
            response = super().form_valid(form)
        except ProtectedError as exc:
            messages.error(
                self.request,
                f"删除失败：别的存档的发射日志仍引用它（{protected_names(exc)}），请先处理。",
            )
            return redirect(self.get_source_url())
        messages.success(self.request, f"已删除存档及其全部内容：{save}")
        return response
