# 路由、表单与页面

> 实现 URL、视图、表单、模板时照本文写。数据模型字段见 [`02-数据模型与数据库.md`](02-数据模型与数据库.md)。

---

## 1. 视图类型与命名约定

| 视图类型 | 基类 | 路由名 | URL |
|---|---|---|---|
| 列表 | `ListView` | `<model>_list` | `/<app>/` |
| 详情 | `DetailView` | `<model>_detail` | `/<app>/<int:pk>/` |
| 新增 | `CreateView` | `<model>_create` | `/<app>/add/` |
| 编辑 | `UpdateView` | `<model>_update` | `/<app>/<int:pk>/edit/` |
| 删除 | `DeleteView` | `<model>_delete` | `/<app>/<int:pk>/delete/` |

- 每个 `urls.py` **必须设 `app_name`**，模板中用 `{% url 'carriers:carrier_detail' pk %}`
- 模板路径：`templates/<app>/<model>_<view>.html`（如 `templates/carriers/carrier_list.html`）

### 登录控制

| 类别 | 登录 |
|---|---|
| 全部 `ListView` / `DetailView` / `HomeView` / `FlightScheduleView` / `CarrierVariantTreeView` | **否**（浏览公开） |
| 全部 `CreateView` / `UpdateView` / `DeleteView` / `FlightLaunchView` / `StageReorderView` / AJAX 写端点 | **是**（`LoginRequiredMixin`） |

**筛选一律用 GET 查询参数**，不要用 POST 提交搜索条件。

---

## 2. 根路由（`config/urls.py`）

| 前缀 | include |
|---|---|
| `admin/` | `admin.site.urls` |
| `accounts/` | `django.contrib.auth.urls`（登录/登出/改密，Django 内置） |
| `''` | `core.urls` |
| `parts/` | `parts.urls` |
| `carriers/` | `carriers.urls` |
| `payloads/` | `payloads.urls` |
| `sites/` | `sites.urls` |
| `stages/` | `stages.urls` |
| `launches/` | `launches.urls` |
| `programs/` | `programs.urls` |
| `spacecraft/` | `spacecraft.urls` |

---

## 3. 路由明细（50 条）

### 3.1 `core` — 首页与天体（4）

| 路由名 | URL | 视图 | 方法 | 登录 | 说明 |
|---|---|---|---|---|---|
| `home` | `/` | `HomeView` | GET | 否 | 首页看板：近期发射 5 条 + 进行中计划 + 在役航天器计数 |
| `body_list` | `/bodies/` | `BodyListView` | GET | 否 | 天体列表（按 `depth` 缩进） |
| `body_detail` | `/bodies/<int:pk>/` | `BodyDetailView` | GET | 否 | 天体详情：其发射场、航天器、计划 |
| `about` | `/about/` | `AboutView` | GET | 否 | 关于页（可简化为静态模板） |

### 3.2 `parts` — 部件库（5）

| 路由名 | URL | 视图 | 登录 | 说明 |
|---|---|---|---|---|
| `part_list` | `/parts/` | `PartListView` | 否 | 按 `part_type`（标签页）与 `manufacturer` 筛选；`select_related` 三个 1:1 子表 |
| `part_detail` | `/parts/<int:pk>/` | `PartDetailView` | 否 | 按 `part_type` 显示对应的专有字段块 |
| `part_create` | `/parts/add/` | `PartCreateView` | 是 | 含超类 + 1:1 子表的一次性录入 |
| `part_update` | `/parts/<int:pk>/edit/` | `PartUpdateView` | 是 | 同上 |
| `part_delete` | `/parts/<int:pk>/delete/` | `PartDeleteView` | 是 | 确认页 |

### 3.3 `carriers` — 运载火箭（6）

| 路由名 | URL | 视图 | 登录 | 说明 |
|---|---|---|---|---|
| `carrier_list` | `/carriers/` | `CarrierListView` | 否 | 按 `series` / `is_reusable` 筛选 |
| `carrier_detail` | `/carriers/<int:pk>/` | `CarrierDetailView` | 否 | **★ 级序列表 + Δv 逐级累加 + 起飞 TWR + 变体树** |
| `carrier_create` | `/carriers/add/` | `CarrierCreateView` | 是 | **含 `CarrierStageFormSet`** |
| `carrier_update` | `/carriers/<int:pk>/edit/` | `CarrierUpdateView` | 是 | 含 FormSet |
| `carrier_delete` | `/carriers/<int:pk>/delete/` | `CarrierDeleteView` | 是 | 提示「其级将一并删除」 |
| `carrier_variants` | `/carriers/<int:pk>/variants/` | `CarrierVariantTreeView` | 否 | `derived_from` 递归血缘树 |

### 3.4 `payloads` — 有效载荷（5）

`payload_list` / `payload_detail` / `payload_create` / `payload_update` / `payload_delete`，URL 与 carriers 同构（`/payloads/…`）。
`payload_create` / `payload_update` 含 `PayloadStageFormSet`。

### 3.5 `stages` — 级与级内燃料罐（5）

| 路由名 | URL | 视图 | 登录 | 说明 |
|---|---|---|---|---|
| `stage_create` | `/stages/add/` | `StageCreateView` | 是 | 独立新增一级（用 GET 参数 `?owner_type=&owner_id=` 指定归属） |
| `stage_update` | `/stages/<int:pk>/edit/` | `StageUpdateView` | 是 | **含 `StageTankFormSet`**（燃料罐在此维护） |
| `stage_delete` | `/stages/<int:pk>/delete/` | `StageDeleteView` | 是 | — |
| `stage_reorder` | `/stages/reorder/` | `StageReorderView` | 是 | **POST only**，批量调整 `stage_order`，返回 JSON |
| `stage_tank_options` | `/stages/tank-options/` | `StageTankOptionsView` | 是 | 可选增强：按直径筛选可挂燃料罐，返回 JSON |

### 3.6 `sites` — 发射场（5）

`site_list` / `site_detail` / `site_create` / `site_update` / `site_delete`，URL 为 `/sites/…`。
列表按 `body` 分组筛选。

### 3.7 `launches` — 发射日志与日程（7）

| 路由名 | URL | 视图 | 登录 | 说明 |
|---|---|---|---|---|
| `flight_list` | `/flights/` | `FlightListView` | 否 | 按 `state`/`carrier`/`payload`/`site` 筛选，分页 |
| `flight_schedule` | `/flights/schedule/` | `FlightScheduleView` | 否 | **★ 核心页**：`state` 为待发的任务按 `planned_ut` 排序分组 |
| `flight_detail` | `/flights/<int:pk>/` | `FlightDetailView` | 否 | — |
| `flight_create` | `/flights/add/` | `FlightCreateView` | 是 | 用于**新建发射计划** |
| `flight_update` | `/flights/<int:pk>/edit/` | `FlightUpdateView` | 是 | — |
| `flight_delete` | `/flights/<int:pk>/delete/` | `FlightDeleteView` | 是 | — |
| `flight_launch` | `/flights/<int:pk>/launch/` | `FlightLaunchView` | 是 | **POST only**，一键执行发射：`PLANNED`/`COUNTDOWN` → `LAUNCHED` 并写 `actual_ut` |

`FlightScheduleView` 的主查询用 `Index(fields=['state', 'planned_ut'])`：
`FlightLog.objects.filter(state__in=[PLANNED, COUNTDOWN]).order_by('planned_ut')`

### 3.8 `programs` — 航天计划与成员（7）

| 路由名 | URL | 视图 | 登录 | 说明 |
|---|---|---|---|---|
| `program_list` | `/programs/` | `ProgramListView` | 否 | 按 `status` / `priority` 筛选 |
| `program_detail` | `/programs/<int:pk>/` | `ProgramDetailView` | 否 | **★ 1:n 聚合页**：按 `object_type` 分 5 区展示成员 + 进度 + 预算 |
| `program_create` | `/programs/add/` | `ProgramCreateView` | 是 | — |
| `program_update` | `/programs/<int:pk>/edit/` | `ProgramUpdateView` | 是 | — |
| `program_delete` | `/programs/<int:pk>/delete/` | `ProgramDeleteView` | 是 | — |
| `programlink_create` | `/programs/<int:program_pk>/link/add/` | `ProgramLinkCreateView` | 是 | 动态：选 `object_type` 后加载对应对象下拉 |
| `programlink_delete` | `/programs/links/<int:pk>/delete/` | `ProgramLinkDeleteView` | 是 | **POST only，无确认页** → 计划详情页的「移除」必须是内联 POST 表单，不能是链接 |

### 3.9 `spacecraft` — 在轨航天器（6）

| 路由名 | URL | 视图 | 登录 | 说明 |
|---|---|---|---|---|
| `spacecraft_list` | `/spacecraft/` | `SpacecraftListView` | 否 | 默认只显示 `is_active=True`；按 `body`/`situation` 筛选 |
| `spacecraft_detail` | `/spacecraft/<int:pk>/` | `SpacecraftDetailView` | 否 | 轨道六要素 + 派生周期/近远拱点 |
| `spacecraft_create` | `/spacecraft/add/` | `SpacecraftCreateView` | 是 | — |
| `spacecraft_update` | `/spacecraft/<int:pk>/edit/` | `SpacecraftUpdateView` | 是 | — |
| `spacecraft_delete` | `/spacecraft/<int:pk>/delete/` | `SpacecraftDeleteView` | 是 | — |
| `spacecraft_orbit_calc` | `/spacecraft/orbit-calc/` | `OrbitCalcView` | 是 | **POST only，AJAX**：传 `body_id`+`sma`+`eccentricity` → 返回周期与近远拱点 |

### 3.10 AJAX 端点约定（只有 3 个）

不引入 DRF（本项目是服务端渲染的多页应用）。统一 JSON 契约：

```json
{ "ok": true,  "data": { ... }, "errors": {} }
{ "ok": false, "data": null,    "errors": { "sma": ["半长轴必须大于 Kerbin 的半径 600000 m。"] } }
```

| 端点 | 入参 | 返回 |
|---|---|---|
| `spacecraft_orbit_calc` | `body_id`, `sma`, `eccentricity` | `period_sec`, `period_days`, `periapsis`, `apoapsis`, `altitude` |
| `stage_reorder` | `stage_ids`（按新顺序的 id 列表） | `ok` |
| `stage_tank_options`（可选） | `diameter` | 可挂燃料罐列表 |

---

## 4. 表单

### 4.1 校验的三层分工（总纲）

| 层 | 放什么 | 例子 |
|---|---|---|
| **DB `CheckConstraint`** | 单表、同表字段之间的规则 | `stage_order >= 1`；`priority` 在 1–5 |
| **模型 `clean()`** | 跨表规则；需要中文提示的业务规则 | `wet_mass >= part.dry_mass`；`sma > body.radius`；`FlightLog` 状态-时间一致性 |
| **表单 `clean()`** | 只在录入时需要、模型不该管的规则 | `stage_order` 在同一次提交内唯一且连续（FormSet 层） |

### 4.2 表单基类（保证模型 `clean()` 真的跑）

`ModelForm` **默认不会调用模型的 `full_clean()`**，只做字段级校验。而本项目的跨表规则都写在模型 `clean()` 里 —— 所以必须显式调。

```python
# core/forms.py
class ModelCleanFormMixin:
    """在 ModelForm 校验链里插入模型的 clean()。

    必要性：本项目把跨表规则（如 FuelTank.wet_mass >= part.dry_mass、
    Spacecraft.sma > body.radius）写在模型的 clean() 里，因为 SQLite 的
    CHECK 不支持子查询。而 ModelForm 默认只做字段级校验，不调 full_clean()，
    于是这些规则在 Web 表单路径上会被完全跳过。本 mixin 补上这一环。
    """

    def clean(self):
        cleaned = super().clean()
        if hasattr(self.instance, "full_clean") and self.is_valid_prefix():
            try:
                self.instance.full_clean(exclude=self._get_excluded_for_full_clean())
            except ValidationError as exc:
                # 把模型层的错误合并进表单错误
                for field, msgs in exc.message_dict.items():
                    target = field if field in self.fields else None
                    for msg in msgs:
                        self.add_error(target, msg)
        return cleaned
```

> ⚠️ `full_clean(exclude=...)` 要排除掉「表单里没有的字段」和「由视图补充的 FK」（如 `Stage.owner_type`），否则会因为「该字段必填但为空」而误报。
>
> ⚠️ **`add_error()` 之后 `form.cleaned_data` 会变成 `None`** —— 任何后续代码访问它都会抛 `AttributeError`。见 §5 的守卫写法。

### 4.3 表单清单

| 表单类 | 基类 | 关键校验 |
|---|---|---|
| `BodyForm` | `ModelForm` | `parent` 不能是自己（模型 CHECK 也会拦） |
| `PartForm` | `ModelForm` + `ModelCleanFormMixin` | 按 `part_type` **条件显示并保存**对应的 1:1 子表（TANK→`FuelTank`、ENGINE→`Engine`、SCIENCE→`ScienceInstrument`） |
| `FuelTankForm` / `EngineForm` / `ScienceInstrumentForm` | `ModelForm` | `wet_mass >= part.dry_mass`；`thrust_vac >= thrust_asl`；`transmit_efficiency` 0–100 |
| `CarrierForm` | `ModelForm` | `code` 正则（由 `CodeModel`/mixin 统一） |
| `PayloadForm` | `ModelForm` | 同上 |
| `SiteForm` | `ModelForm` + `ModelCleanFormMixin` | **`body` 必填**；`-90 ≤ latitude ≤ 90`；`-180 ≤ longitude ≤ 180`；`code` 正则 |
| `FlightLogForm` | `ModelForm` | **状态-时间一致性**（见 §4.4） |
| `ProgramForm` | `ModelForm` | `priority` 1–5；`end_ut >= start_ut` |
| `ProgramLinkForm` | `ModelForm` | `object_type` 与「恰好一个对象」一致 |
| `SpacecraftForm` | `ModelForm` | `sma > body.radius`；`ORBITING`/`DOCKED` 时 `0 ≤ e < 1`；`0 ≤ inclination ≤ 180` |

**`PartForm` 的实现要点**（三个 1:1 子表条件保存）：`part_type` 是选择器；用 JS 显示/隐藏三个子表字段块；`save()` 里按 `part_type` 创建或更新对应子表，并把另外两个子表（若存在）删掉。`part_type` 变更时尤其要处理旧子表的清理。

### 4.4 `FlightLogForm` 的状态-时间一致性

```python
def clean(self):
    cleaned = super().clean()
    state, actual = cleaned.get("state"), cleaned.get("actual_ut")
    if state == FlightState.PLANNED and actual is not None:
        self.add_error("actual_ut", "计划中的任务不应填写实际发射时间。")
    if state in (FlightState.LAUNCHED, FlightState.FAILED) and actual is None:
        self.add_error("actual_ut", "已发射/失败的任务必须填写实际发射时间。")
    return cleaned
```

同一个规则也写在 `FlightLog.clean()`（数据层兜底），两处保持一致。

### 4.5 `result_code` 必须是选择器，不是自由输入框

`result_code` 是有语义的编码：

| 值 | 含义 |
|---|---|
| `NULL` | 尚未执行 |
| `-2` | 台架中止 |
| `-1` | 任务失败（设计缺陷） |
| `0` | 成功 |
| `>0` | **第 n 级失效** |

**交互设计**：不用 `IntegerField` 直接输入。做成「结果选择器」：

- 单选组：`成功` / `失败` / `台架中止` / `未执行`
- 选「失败」时，出现一个**动态下拉**让玩家选「哪一级失效」→ 该级 `stage_order` 即 `result_code` 的值，另一选项「非级失效的设计缺陷」→ `-1`

---

## 5. `Stage` 的 FormSet（本项目技术难点）

### 5.1 为什么必须两套 FormSet

`Stage` 用 `owner_type` + 双可空 FK 多态（见 `01` §5.3）。`inlineformset_factory` **要求一个确定的 `fk_name`**，所以：

| 场景 | 工厂 | `fk_name` | FormSet 类 |
|---|---|---|---|
| 火箭新增/编辑 | `inlineformset_factory(CarrierModel, Stage, formset=CarrierStageFormSet, fk_name='carrier', extra=2, can_delete=True)` | `'carrier'` | `CarrierStageFormSet` |
| 载荷新增/编辑 | 同上 | `'payload'` | `PayloadStageFormSet` |
| 火箭 Admin 内联 | `fk_name='carrier', extra=0, can_delete=True` | `'carrier'` | `CarrierStageInlineFormSet` |
| 载荷 Admin 内联 | `fk_name='payload'` | `'payload'` | `PayloadStageInlineFormSet` |

`owner_type` **不出现在表单里**（从 `fields` 排除），由视图/Admin 在 `save` 阶段按路径填 `'CARRIER'` 或 `'PAYLOAD'`。

```python
# stages/formsets.py
class BaseStageFormSet(forms.BaseInlineFormSet):
    owner_type: str = ""       # 子类指定 StageOwnerType.CARRIER / .PAYLOAD
    owner_field: str = ""      # 子类指定 'carrier' / 'payload'

    def save_new(self, form, commit=True):
        obj = super().save_new(form, commit=False)
        setattr(obj, "owner_type", self.owner_type)   # ★ 自动填充
        if commit:
            obj.save()
        return obj

    def save_existing(self, form, instance, commit=True):
        setattr(instance, "owner_type", self.owner_type)
        return super().save_existing(form, instance, commit)
```

> 填充责任放在 FormSet 的 `save_*` 钩子上（而不是视图里）—— 这样 Admin 与前台**共用同一套逻辑**，不会漏。

### 5.2 `stage_order` 的唯一性与连续性校验

```python
    @staticmethod
    def _row_value(form, field):
        """安全读值。

        ⚠️ add_error() 会把 cleaned_data 置为 None —— 无条件访问会抛 AttributeError。
        """
        if form.errors or not getattr(form, "cleaned_data", None):
            return None
        return form.cleaned_data.get(field)

    def clean(self):
        super().clean()
        seen = {}
        for form in self.forms:
            if form in self.deleted_forms:      # ★ 必须排除已删除的行
                continue
            order = self._row_value(form, "stage_order")
            if order is None:
                continue
            if order in seen:
                form.add_error("stage_order", f"级序号 {order} 与另一级重复。")
            else:
                seen[order] = form

        # 连续性：最终保留的级序号必须是 1..n 不间断
        # 只在所有行都通过唯一性校验时才判断，避免错误叠加、提示难懂
        if any(f.errors for f in self.forms if f not in self.deleted_forms):
            return
        orders = sorted(seen.keys())
        if not orders:
            return                              # 允许全部删除（先建火箭后补级）
        if orders != list(range(1, len(orders) + 1)):
            raise ValidationError(f"级序号必须是 1 到 {len(orders)} 连续，当前为 {orders}。")
```

> **必须排除 `deleted_forms`** —— 否则「删掉第 2 级、同时新增一个第 2 级」这个最常见的编辑操作会被误判为重复（被删的行仍在表单数据里）。

### 5.3 `StageTankFormSet` 与两级嵌套

燃料罐在级内：`inlineformset_factory(Stage, StageTank, extra=1, can_delete=True)`。

**级内挂燃料罐是两级嵌套 FormSet**（火箭 → 级 → 燃料罐）。若在 P2 的时间盒内无法稳定实现，**启用降级方案**：

| | 完整版 | 降级版 |
|---|---|---|
| 火箭表单 | 级 FormSet + 级内燃料罐 FormSet（两级嵌套） | 只管到「级 + 引擎 + 引擎数量」 |
| 燃料罐维护 | 在火箭编辑页内联完成 | 在 `stage_update` 独立页用 `StageTankFormSet` 管理 |
| 验收差异 | 「加级 → 级内加罐 → 提交」一步完成 | 需两次保存 |

**降级触发条件**（满足任一即降级）：① 级内嵌套的 `__prefix__` 双层替换无法在 2 小时内调通；② 提交后出现跨级串行（燃料罐落到错误的级）；③ 递归处理嵌套 `DELETE` 无法稳定。

`stage_update` 页**无论走哪个版本都必须存在**，所以降级不会造成返工。

### 5.4 ★ 客户端动态增删（`static/js/stage_formset.js`）

不用 React/Vue，纯 JS + `<template>`：

1. **「+ 添加一级」**：克隆 Django 提供的 `empty_form`（用 `<template id="empty-stage-form">` 渲染 `formset.empty_form`），把占位符 `__prefix__` 替换为当前索引
2. **「移除」**：**只勾选 `DELETE` 隐藏域 + 隐藏该行，绝不删除 DOM 节点**（否则 FormSet 索引错乱）。若该行内还有嵌套的 `StageTank` 行，**必须递归勾选它们的 `DELETE`** —— 这是最易漏的一处
3. **`TOTAL_FORMS` 只增不减**（等于已渲染的行数，含被标记删除的行）。**写成「减去删除数」会导致静默丢级或跨级串行** —— 本项目最坏的 bug 类型
4. `INITIAL_FORMS` 等于初始从数据库加载的行数，不变
5. **顺序即 `stage_order`**：用 HTML5 `draggable` 拖拽排序，提交前按 DOM 顺序重写各行的 `stage_order` 隐藏输入；或调 `stage_reorder` AJAX
6. 页面必须给**方向提示**：`ℹ 本页自上而下显示，底部为第 1 级（最先点火的起飞级）。Δv 从第 1 级起向上累加。`

**无 JS 兜底**：服务端 `extra=2` 预渲染空行，使玩家至少能反复保存逐级累加。

### 5.5 `stage_reorder` 的实现（会撞唯一约束）

批量改 `stage_order` 时，逐条更新会在中间态撞上 `uniq_carrier_stage_order`（例如 1,2,3 → 3,1,2）。

```python
with transaction.atomic():
    max_order = Stage.objects.filter(carrier=carrier).aggregate(m)["m"] or 0
    # 第一步：挪到临时区间（现有最大值之上）
    for i, stage in enumerate(stages):
        stage.stage_order = max_order + 1000 + i
        stage.save(update_fields=["stage_order"])
    # 第二步：写入最终序号
    for i, stage in enumerate(stages, start=1):
        stage.stage_order = i
        stage.save(update_fields=["stage_order"])
```

> **不可用负数做临时值** —— `CheckConstraint(stage_order__gte=1)` 会拒绝。

### 5.6 `ProgramLinkCreateView` 的多态对象选择

`object_type` 是 `ChoiceField`；选定后加载对应对象的下拉。推荐做法（不引入 AJAX）：

1. `ProgramLinkForm.__init__` 里**一次性把五类对象的选项都查出来**（各自加前缀，如 `"C:12"`、`"P:5"`），放入一个 `ChoiceField` 的 `choices`
2. 用 `optgroup` 或前缀区分类型；提交时由 `object_type` + 选中值解析出具体对象
3. 数据量小（单玩家），一次查询五张表完全可接受，省掉一轮 AJAX 与前端状态管理

---

## 6. 页面清单

Bootstrap 5；状态用 `badge` 着色；每个列表页都要有**空状态**提示。

| # | 页面 | 模板 | 关键内容 |
|---|---|---|---|
| 1 | 首页看板 | `core/home.html` | 近期发射 5 条、进行中计划卡片、在役航天器计数 |
| 2 | 天体列表/详情 | `core/body_*.html` | 树形缩进（按 `depth`） |
| 3 | 部件列表 | `parts/part_list.html` | `part_type` 标签页、直径/类型筛选、造价排序 |
| 4 | 部件详情 | `parts/part_detail.html` | 按类型显示三套专有字段块 |
| 5 | 部件表单 | `parts/part_form.html` | `part_type` 切换时显示对应子表字段 |
| 6 | 火箭列表 | `carriers/carrier_list.html` | 系列分组、变体标记 |
| 7 | **火箭详情** | `carriers/carrier_detail.html` | **★ 级序列表（降序）+ Δv 逐级累加条 + 起飞 TWR + 变体树** |
| 8 | **火箭表单** | `carriers/carrier_form.html` | **★ 级 FormSet 动态增删** |
| 9 | 载荷列表/详情/表单 | `payloads/*` | 同火箭 |
| 10 | 级表单 | `stages/stage_form.html` | `StageTankFormSet`（降级版下燃料罐在此维护） |
| 11 | 发射场列表/表单 | `sites/*` | 天体选择、经纬度 |
| 12 | 发射日志列表 | `launches/flight_list.html` | 多维筛选、分页 |
| 13 | **发射日程** | `launches/flight_schedule.html` | **★ 待发任务按 `planned_ut` 分组**；每条有「执行发射」按钮 |
| 14 | 发射详情/表单 | `launches/flight_*.html` | `planned_ut` 与 `actual_ut` 并列；`result_code` 结果选择器 |
| 15 | 计划列表 | `programs/program_list.html` | 状态/优先级筛选、进度条 |
| 16 | **计划总览** | `programs/program_detail.html` | **★ 按 `object_type` 分 5 区展示成员**；预算执行率；发射完成率 |
| 17 | 计划成员表单 | `programs/programlink_form.html` | 动态对象选择 |
| 18 | 在役航天器列表 | `spacecraft/spacecraft_list.html` | 按天体/状态筛选；**周期与近远拱点列** |
| 19 | 航天器详情/表单 | `spacecraft/spacecraft_*.html` | 轨道要素 + **实时周期计算**（AJAX） |

外加 `templates/base.html` 与 `includes/{_navbar,_footer,_messages,_formhelpers}.html`。

### 计算值的展示规范

| 量 | 格式 | 着色/提示 |
|---|---|---|
| Δv | 大字，`3 100 m/s` | 逐级一根横条，长度按 Δv 占比 |
| TWR | 保留 2 位小数 | 按 `twr_verdict()` 的级别着色（见 `03` §3 阈值表） |
| 轨道周期 | **同时显示秒与「游戏天」** | 并列出 `cached_period_sec` 抄录值，偏差 > 1% 时提示 |
| 近/远拱点 | **显示为相对表面的高度**（`r − Body.radius`） | — |
| `sma` 输入框 | 常驻提示「半长轴，非高度；Kerbin 半径 600 km」 | 校验 `sma > body.radius` |

### 状态徽章建议配色

| 枚举 | 值 → 颜色 |
|---|---|
| `FlightState` | `PLANNED` secondary ｜ `COUNTDOWN` info ｜ `LAUNCHED` success ｜ `FAILED` danger ｜ `CANCELLED` dark |
| `ProgramStatus` | `PLANNED` secondary ｜ `ACTIVE` primary ｜ `COMPLETED` success ｜ `CANCELLED` dark |
| `Situation` | `ORBITING` primary ｜ `LANDED`/`SPLASHED` success ｜ `ESCAPING` info ｜ `FLYING` warning ｜ `DOCKED` secondary ｜ `DESTROYED` danger |

### 前端注意

- 图标用 **Bootstrap Icons**（CDN），不用 Font Awesome
- **不要开 `USE_THOUSAND_SEPARATOR`** —— 会把 `type="number"` 的 UT 输入框值变成 `NaN`。要千分位就自定义模板过滤器
- 「执行发射」按钮用 `modal` 确认；Bootstrap JS 加载失败时提供直链 POST 兜底（`<noscript>`）
