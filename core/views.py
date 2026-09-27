"""前台视图：**单端点弹窗增删改**（文档 12）。

增删改不再有独立路由，全部 POST 回所在列表页自己的 URL，靠 `action` 字段分流：

    POST /saves/3/payloads/
        action=create                          → 新建
        action=update & pk=7                   → 修改
        action=delete & pk=7 & confirmed=yes   → 删除

本文件提供两个共用基类：

| 基类 | 用途 |
|---|---|
| `DialogCrudMixin` | `post` / `_handle_save` / `_handle_delete` 三个方法 + 行数据组装 |
| `SaveScopedCrudView` | 存档下某个集合的列表（按 `program` 过滤） |
| `CrudListView` | 没有存档归属的列表（参考数据） |

⚠️ 外键属性名是 `program`，绝不能写成 `save`（`save` 会遮蔽 `Model.save()`）。
"""

from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, TemplateView

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


class DialogCrudMixin:
    """「列表 + 弹窗增删改」的公共实现（文档 12 第 4–5 节）。

    子类必须给 `model` / `form_class` / `template_name` / `context_object_name`，
    并实现两个钩子：`get_scoped_object(pk)`、`build_form(data, instance, prefix)`。
    可选：`select_related`、`get_rows()` 覆写（给行补派生列如周期/结果）。
    """

    open_dialog = None       # "create" / "edit"：校验失败时设值，模板据此输出 data-open
    open_pk = None
    bound_form = None
    select_related = ()

    # ---------- 子类钩子 ----------
    def get_scoped_object(self, pk):
        """按 pk 取对象，并校验它落在本页面允许的范围内。取不到返回 None。"""
        raise NotImplementedError

    def build_form(self, data, instance, prefix=None):
        """构造该模型在此页面上的 ModelForm（带 program / rocket 等外部参数）。"""
        raise NotImplementedError

    def protected_error_message(self, exc):
        return f"删除失败：仍有数据引用它（{protected_names(exc)}），请先处理这些数据。"

    # ---------- 行数据 ----------
    def get_rows_source(self):
        return self.object_list

    def get_rows(self):
        """给每行配上编辑表单与两个弹窗的 id（模板里就不必拼接字符串）。"""
        return [
            {
                "obj": obj,
                "form": self.build_form(None, obj, prefix=f"e{obj.pk}"),
                "prefix": f"e{obj.pk}",
                "edit_id": f"dlg-edit-{obj.pk}",
                "del_id": f"dlg-del-{obj.pk}",
            }
            for obj in self.get_rows_source()
        ]

    def refresh_object_list(self):
        """POST 路径下 ListView 的 `object_list` 不会自动刷新，校验失败要重渲染时手动取一次。"""
        get_queryset = getattr(self, "get_queryset", None)
        if get_queryset is not None:
            self.object_list = get_queryset()

    # ---------- GET ----------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rows = self.get_rows()
        new_form = self.build_form(None, None, prefix="new")
        if self.bound_form is not None:
            if self.open_dialog == "create":
                new_form = self.bound_form                       # 新建校验失败：带错误的表单
            elif self.open_dialog == "edit":
                for row in rows:
                    if row["obj"].pk == self.open_pk:
                        row["form"] = self.bound_form            # 编辑校验失败：替换该行表单
        for row in rows:
            row["open_edit"] = self.open_dialog == "edit" and self.open_pk == row["obj"].pk
        ctx["rows"] = rows
        ctx["new_form"] = new_form
        ctx["open_new"] = self.open_dialog == "create"
        ctx["open_pk"] = self.open_pk
        return ctx

    # ---------- POST ----------
    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "delete":
            return self._handle_delete(request)
        if action in ("create", "update"):
            return self._handle_save(request, action)
        messages.error(request, "未知操作。")
        return redirect(request.path)

    def _handle_save(self, request, action):
        instance = None
        if action == "update":
            instance = self.get_scoped_object(request.POST.get("pk"))
            if instance is None:
                messages.error(request, "要修改的记录不存在。")
                return redirect(request.path)
        form = self.build_form(
            request.POST, instance, prefix=request.POST.get("prefix") or None
        )
        if not form.is_valid():
            # 校验失败**不能 redirect**：否则弹窗里的错误与用户输入全丢（文档 12 第 4.3 节）
            self.bound_form = form
            self.open_dialog = action
            self.open_pk = instance.pk if instance else None
            self.refresh_object_list()
            return self.render_to_response(self.get_context_data())
        form.save()
        messages.success(request, "已保存。" if instance else "已新增。")
        return redirect(request.path)

    def _handle_delete(self, request):
        if request.POST.get("confirmed") != "yes":
            messages.error(request, "删除未确认。")
            return redirect(request.path)
        obj = self.get_scoped_object(request.POST.get("pk"))
        if obj is None:
            messages.error(request, "要删除的记录不存在。")
            return redirect(request.path)
        try:
            obj.delete()
        except ProtectedError as exc:
            messages.error(request, self.protected_error_message(exc))
            return redirect(request.path)
        messages.success(request, "已删除。")
        return redirect(request.path)


class SaveScopedCrudView(DialogCrudMixin, ListView):
    """存档下某个集合的「列表 + 弹窗增删改」（`/saves/<pk>/<slug>/`，文档 12 第 5.1 节）。

    ⚠️ 过滤字段是 `program`（绝不能写成 `save`，那会遮蔽 `Model.save()`）。
    """

    save = None

    def dispatch(self, request, *args, **kwargs):
        self.save = get_object_or_404(Save, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = self.model.objects.filter(program=self.save)
        return qs.select_related(*self.select_related) if self.select_related else qs

    def get_scoped_object(self, pk):
        """只允许操作**属于本存档**的对象（防越权改别人的数据）。"""
        if not (pk and str(pk).isdigit()):
            return None
        return self.model.objects.filter(pk=pk, program=self.save).first()

    def build_form(self, data, instance, prefix=None):
        return self.form_class(data, instance=instance, program=self.save, prefix=prefix)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["save"] = self.save
        return ctx


class CrudListView(DialogCrudMixin, ListView):
    """无存档归属的「列表 + 弹窗增删改」基类（参考数据：引擎/燃料罐/科学设备，文档 12 §5.4）。

    与 `SaveScopedCrudView` 的唯一区别：`get_scoped_object()` 不按 `program` 过滤，
    表单也不需要 `program` 参数（这三张表没有存档外键）。
    """

    def get_scoped_object(self, pk):
        if not (pk and str(pk).isdigit()):
            return None
        return self.model.objects.filter(pk=pk).first()

    def build_form(self, data, instance, prefix=None):
        return self.form_class(data, instance=instance, prefix=prefix)


class HomeView(TemplateView):
    """主页 `/`：**暂空**，等后续开发补充（文档 11 第 2.1 节）。

    不要顺手把统计 / 近期发射之类的块搬进来 —— 那些块留在存档列表 `/saves/` 里，
    主页放什么等后续设计。
    """

    template_name = "core/home.html"


class SaveListView(DialogCrudMixin, TemplateView):
    """存档列表 `/saves/`：存档的弹窗增删改 + 全局统计 + 近期发射（文档 11 §4.3 / 12 §5.5）。

    `Save` 自己就是列表数据，所以直接在这个视图上挂弹窗增删改（没有 `program` 归属）。
    删存档要保留两项特殊处理：确认弹窗**列出将连带删除的各项数量**，以及
    「别的存档的发射日志仍引用它」的 PROTECT 提示（`Save.delete()` 的级联顺序在模型层）。
    """

    template_name = "core/save_list.html"
    model = Save
    form_class = SaveForm
    context_object_name = "saves"
    _rows_source = None

    # ---- 弹窗增删改的钩子 ----
    def get_scoped_object(self, pk):
        if not (pk and str(pk).isdigit()):
            return None
        return Save.objects.filter(pk=pk).first()

    def build_form(self, data, instance, prefix=None):
        return SaveForm(data, instance=instance, prefix=prefix)

    def protected_error_message(self, exc):
        return f"删除失败：别的存档的发射日志仍引用它（{protected_names(exc)}），请先处理。"

    def get_rows_source(self):
        if self._rows_source is None:
            self._rows_source = Save.objects.annotate(
                rocket_total=Count("rockets", distinct=True),
                flight_total=Count("flights", distinct=True),
            )
        return self._rows_source

    def get_rows(self):
        rows = super().get_rows()
        for row in rows:
            save = row["obj"]
            counts = [
                ("火箭", save.rockets.count()),
                ("载荷", save.payloads.count()),
                ("发射场", save.sites.count()),
                ("航天器", save.spacecraft.count()),
                ("发射日志", save.flights.count()),
            ]
            row["related_counts"] = counts
            row["delete_confirm"] = (
                "将删除：" + "、".join(f"{label} {n}" for label, n in counts) + "。此操作不可恢复。"
            )
        return rows

    # ---- GET ----
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["save_rows"] = self.get_rows_source()
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
