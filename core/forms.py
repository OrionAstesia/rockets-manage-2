"""通用表单基类（改造文档 10 第 5.1 节）。

这里只放两件与业务无关的事：把日期字段换成本地原生日期输入（不需要 JS），
以及把 `program`（所属存档）从 URL/上下文注入而不让用户选。
"""

from django import forms

from ops.models import Save


class BaseModelForm(forms.ModelForm):
    """所有 ModelForm 的共同基类：日期用 `type=date`，控件套上 Bootstrap 类。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(field, forms.DateField) and hasattr(widget, "input_type"):
                # 注意要改 input_type 而不是 attrs["type"]，否则渲染出两个 type 属性、
                # 浏览器取第一个（text），原生日期选择器就不生效了。
                widget.input_type = "date"
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs.setdefault("rows", 3)
            else:
                widget.attrs.setdefault("class", "form-control")


class ProgramScopedFormMixin:
    """把 program（所属存档）从 URL/上下文注入，表单里不显示该字段。

    为什么必须显式注入：`program` 是必填外键且不在表单字段里，
    `ModelForm._post_clean` 会调用 `instance.full_clean(exclude=表单外字段)`，
    于是 `program` 的必填校验被跳过；若不注入，保存时会 IntegrityError。

    ⚠️ 属性名是 `program`，绝不能写成 `save` —— `save` 会遮蔽 `Model.save()`。
    """

    def __init__(self, *args, program=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("program", None)          # 不显示、也不接受用户提交
        if program is not None:
            self.instance.program = program       # 新建时由视图传入
        # 供子类按存档过滤外键下拉。注意用 getattr：未保存且未设 program 的实例上
        # 访问 instance.program 会抛 RelatedObjectDoesNotExist（它继承 AttributeError，所以 getattr 安全）
        self.program = getattr(self.instance, "program", None)


class SaveForm(BaseModelForm):
    """存档表单：名称 / 开始日期 / 模式。"""

    class Meta:
        model = Save
        fields = ["name", "start_date", "game_mode"]
