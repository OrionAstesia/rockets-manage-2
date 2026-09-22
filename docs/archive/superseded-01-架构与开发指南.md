# 架构与开发指南

> 开工前读本文 + [`02-数据模型与数据库.md`](02-数据模型与数据库.md)。这两份是必读，其余按需查。

---

## 1. 项目是什么

KSP 玩家的**发射计划与任务记录管理工具**。单机、自用、单人。

要做的六件事：
1. **部件库**：燃料罐、引擎、科学设备
2. **载具**：火箭与载荷，各自含**有序的级结构**（级内有引擎与燃料罐）
3. **发射场**：含所属天体与坐标
4. **发射日志**：计划发射（`planned_ut`）与实际发射（`actual_ut`）分离 —— **这是「安排发射计划」的核心**
5. **航天计划**：1 个计划统辖 n 个其他对象（火箭/载荷/发射日志/发射场/航天器）
6. **在轨航天器**：轨道六要素 + 派生的周期与近远拱点

**附带能力**：Δv 与推重比计算（从级结构算出）、发射日程视图。

**v1 明确不做**：乘员 kerbal 名册、多用户与权限、数据导入导出、KSP 存档（`.sfs`）解析、整流罩/分离环等结构件细分建模、部件级自动计算器。**不要在实现时顺手加上。**

---

## 2. 技术栈

| 项 | 选择 |
|---|---|
| 框架 | **Django 5.2** |
| 数据库 | **SQLite**（`db.sqlite3`） |
| Python | **3.10**，conda 环境名 **`rocket`** |
| 依赖 | `Django==5.2.*`、`numpy>=1.26` —— **就这两个** |
| 前端 | Django 模板 + Bootstrap 5（CDN）+ 原生 JS，**无构建链** |
| 测试 | `manage.py test` |

**为什么是 Django**：14 张表的 CRUD 由 Admin 覆盖，省掉约 70% 的手写代码，能把时间花在级结构与发射计划这些真正的业务上。

**不需要的依赖**：`pymysql`、`wtforms`、`passlib` —— 分别由 Django ORM、Django Forms、Django 内置密码哈希替代。

### 环境（必看，本机有坑）

```powershell
conda create -n rocket python=3.10 -y
conda activate rocket
pip install "Django==5.2.*" "numpy>=1.26"
python -c "import django; print(django.get_version())"   # 必须是 5.2.x
```

- ⚠️ **PATH 上的 `python` 是 `D:\MinGW\bin\python.exe`，没有 Django。** 必须 `conda activate rocket`。
- ⚠️ **`conda` 不在 PATH**，可执行文件在 `F:\Anaconda\Scripts\conda.exe`。必要时用全路径。
- 不要用 `OrionDB` 环境（Python 3.9，缺依赖），也不要污染 `rag` 环境。
- 经测试，rocket 环境中的 django 版本为 5.2.17

---

## 3. 目录结构

```
rockets-manage-2/
├── manage.py
├── requirements.txt
├── .gitignore
├── db.sqlite3                      # 运行后生成（已 gitignore）
├── config/
│   ├── settings/{base,dev,prod}.py  # 拆三个文件
│   ├── urls.py                      # 根路由
│   ├── wsgi.py
│   └── asgi.py
├── core/            # Body + 首页 + 公共基类
│   ├── mixins.py                    # CodeModel / TimeStampedModel
│   ├── constants.py                 # G0 / FUEL_UNIT_MASS / KERBIN_DAY
│   ├── models.py                    # Body
│   └── views.py / urls.py / admin.py
├── parts/           # PartCatalog FuelTank Engine ScienceInstrument
├── carriers/        # CarrierModel
├── payloads/        # PayloadModel
├── stages/          # Stage StageTank + formsets.py
├── sites/           # Site
├── launches/        # FlightLog + 发射日程
├── programs/        # Program ProgramLink
├── spacecraft/      # Spacecraft
├── services/        # ★ 领域计算，不依赖 Django 视图
│   ├── orbital.py                   # 周期 / 近远拱点 / 速度
│   ├── deltav.py                    # 齐奥尔科夫斯基 / 推重比
│   └── stats.py                     # 计划进度 / 统计聚合
├── templates/       # base.html + includes/ + 各 app 子目录
├── static/{css,js}/
└── docs/            # 本手册集；docs/archive/ 为设计过程存档
```

**每个 app 的标准文件**：`models.py`、`views.py`、`forms.py`、`urls.py`、`admin.py`、`migrations/`，按需加 `formsets.py`（只有 `stages` 需要）。

---

## 4. 分层职责（照这个写，别越界）

| 层 | 位置 | 职责 | **禁止** |
|---|---|---|---|
| 模型 | `<app>/models.py` | 表结构、约束、`clean()` 业务校验、简单 `@property` | 不碰 HTTP |
| 服务 | `services/*.py` | 物理计算、统计聚合、跨模型事务 | **不 import 视图或 request** |
| 表单 | `<app>/forms.py` | 输入校验、`ModelForm`、`FormSet` | 不直接查库 |
| 视图 | `<app>/views.py` | 编排：取数 → 调服务 → 渲染 | **不写业务规则** |
| Admin | `<app>/admin.py` | `list_display`/`list_filter`/内联 | — |
| 路由 | `<app>/urls.py` | URL → 视图 | — |

**`services/` 独立于 app 的意义**：纯函数、无请求上下文，可被 Admin、视图、管理命令、单元测试**共同复用**，且能直接断言数值。这是本项目最值得投入的架构决定 —— 全部物理计算都在这里，且必须带单元测试。

---

## 5. 三个最易出错的约定（动手前背下来）

### 5.1 `stage_order` 方向 —— 计算升序、渲染降序

| | 约定 |
|---|---|
| `stage_order = 1` | **最先点火、最下面那一级**（起飞级） |
| 递增 | 向上递增，最大值 = 最上一级 |
| **页面渲染** | 按 `stage_order` **降序自上而下**（最上级在表格顶部）—— 与火箭外观一致 |
| **Δv 计算** | 从 `stage_order = 1` 起**升序**累加；算第 1 级时 `m₀` 要含**上方全部级 + 载荷** |

升序计算与降序渲染并存是**有意的**：计算遵循质量累加顺序，渲染要让玩家看到物理形状。**这是全项目最容易弄反的地方**，`05` 的详情页模板与 `06` 的 `vehicle_delta_v()` 都要有测试卡住。

### 5.2 `sma` 不等于高度

`Spacecraft.sma` 是**轨道半长轴**（天体中心到轨道），**高度 = `sma − Body.radius`**。Kerbin 半径 600 km，混淆两者会产生 600 km 量级的错误。录入表单必须常驻提示，`clean()` 里校验 `sma > body.radius`。

> 设计阶段这里错过两次，所以写进必读项。

### 5.3 多态 FK 不用 `GenericForeignKey`

`Stage` 与 `ProgramLink` 用 **`owner_type` + 多个可空 FK + CHECK 恰好一个非空**：

- ❌ `GenericForeignKey` 依赖 ContentType，**无法建立数据库级外键与 CHECK**；`GenericTabularInline` 会绕过约束。
- ❌ 两张平行表（`CarrierStage` / `PayloadStage`）结构完全一样，会产生双份表单、路由、校验。
- ✅ 一张表 + `owner_type` 判别。

**代价**：`inlineformset_factory` 需要确定的 `fk_name`，所以要为 `carrier` / `payload` **各生成一套 FormSet**，并在保存时自动填 `owner_type`。

Admin 侧同理：`Stage` 在 `CarrierModelAdmin` / `PayloadModelAdmin` 里各用**一个普通 `TabularInline`**（分别 `fk_name='carrier'` / `'payload'`），不用 Generic 内联；`ProgramLink` 用**独立的 `ProgramLinkAdmin` 页**维护，不在 `ProgramAdmin` 里内联。

---

## 6. 编码规范

### 6.1 模型
- 所有字段带 `verbose_name`（中文），`Meta` 带中文 `verbose_name`/`verbose_name_plural`
- 易错字段带 `help_text`（如 `result_code` 的语义、`stage_order` 的方向）
- 用 `CheckConstraint(condition=...)` —— **Django 5.1+ 的官方关键字是 `condition=`**，`check=` 是旧名
- 带 `code` 的 11 张表继承 `CodeModel`；需要时间戳的继承 `TimeStampedModel`
- 跨表规则放 `clean()`（SQLite 的 CHECK 不支持子查询）

### 6.2 路由命名
Django 通用视图惯例，`urls.py` 里**必须设 `app_name`**，模板中用 `{% url 'carriers:carrier_detail' pk %}`：

| 视图类型 | 路由名 | URL |
|---|---|---|
| 列表 | `<model>_list` | `/<app>/` |
| 详情 | `<model>_detail` | `/<app>/<int:pk>/` |
| 新增 | `<model>_create` | `/<app>/add/` |
| 编辑 | `<model>_update` | `/<app>/<int:pk>/edit/` |
| 删除 | `<model>_delete` | `/<app>/<int:pk>/delete/` |

### 6.3 视图
- 列表/详情用 `ListView`/`DetailView`；增改用 `CreateView`/`UpdateView`；删用 `DeleteView`
- **筛选一律用 GET 查询参数**，不要用 POST 提交搜索条件（可收藏、可回退）
- 列表页必须 `select_related` / `prefetch_related`，禁止 N+1
- 分页 20（大列表 50）

### 6.4 模板
- `templates/base.html` 为骨架，`templates/includes/` 放 `_navbar.html`、`_footer.html`、`_messages.html`、`_formhelpers.html`
- 每 app 一个子目录：`templates/carriers/carrier_list.html` 等
- 状态用 Bootstrap `badge` 着色；空列表要有**空状态提示**

### 6.5 时间与单位
- **游戏时间统一 `FloatField` 存 UT 秒**，不用 `DateField`/`DateTimeField`
- 质量 t、推力 kN、比冲 s、距离 m、角度 °、造价 √
- 展示层再把秒换算成「游戏天」（`KERBIN_DAY = 21600`）

---

## 7. 权限与安全

| 项 | 做法 |
|---|---|
| 登录 | **列表与详情公开；增/改/删/领域写操作必须 `LoginRequiredMixin`** |
| 认证 | 用 Django 内置 `auth`：`django.contrib.auth.urls` 提供登录/登出/改密。**v1 不做注册页**，用 `createsuperuser` 建单用户 |
| CSRF | Django 中间件默认开启，**保持开启**；所有删除走 `DeleteView`（仅 POST） |
| SQL 注入 | 只用 ORM，**代码中不出现裸 SQL** |
| `SECRET_KEY` | `settings/base.py` 从环境变量读，`dev.py` 用开发默认值；**不入库** |
| `DEBUG` | `dev.py` = `True`，`prod.py` = `False`（占位即可） |

---

## 8. 错误处理

| 场景 | 做法 |
|---|---|
| `ProtectedError` | 删除被引用的对象（引擎、燃料罐、天体、有发射记录的火箭/发射场）会抛。**必须在视图/Admin 里捕获，转成 `messages.error()` 友好提示**，否则用户看到 500 |
| 表单校验失败 | Django 默认保留用户输入并回显错误；模板用 `_formhelpers.html` 统一渲染 |
| 提示消息 | 用 `messages` 框架（`success`/`info`/`warning`/`error`），`base.html` 里渲染 |
| 404 / 500 | 加 `templates/404.html`、`templates/500.html` |

---

## 9. 里程碑与阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P0 地基** | 环境、项目骨架、9 个 app、`Body` + fixture、`services/orbital.py` + 单测 | `runserver` 起得来；`/admin/` 能登录；17 个天体可见；`manage.py test` 全绿 |
| **P1 部件库** | `parts` 四模型 + Admin + 列表/详情页 + 部件种子数据 | Admin 能录燃料罐/引擎/科学设备；列表按类型筛选正常 |
| **P2 载具与级** | `carriers`/`payloads`/`sites` + `stages` + FormSet 动态增删 + `services/deltav.py` | 能建含 ≥3 级、每级挂 ≥2 种燃料罐的火箭；详情页显示逐级 Δv 与起飞 TWR |
| **P3 发射与计划** | `launches` + 发射日程 + `programs` + 计划总览 + `services/stats.py` | 「安排 → 发射 → 记录」闭环可用；计划总览按类型聚合展示成员 |
| **P4 在轨与统计** | `spacecraft` + 轨道 AJAX 计算 + 首页看板 | 航天器录入后实时显示周期与近远拱点；首页显示近期发射 |

**依赖顺序**：P0 → P1 → P2 → P3 → P4。P0/P1 无业务风险，**P2 是技术风险最高的阶段**（多级 FormSet）。

---

## 10. 常见陷阱清单

实现时逐条对照：

1. `stage_order` 渲染方向与计算方向弄反 → 见 §5.1
2. `sma` 当成高度用 → 见 §5.2
3. 想用 `GenericForeignKey` 省事 → 见 §5.3，不行
4. `stage_reorder` 重排时先写负数临时序号 → **会撞 `stage_order >= 1` 的 CHECK**。正确做法：先取「现有最大值 + 偏移」作为临时区间，再写最终值，并在 `transaction.atomic()` 里做
5. FormSet 里无条件访问 `form.cleaned_data` → `add_error()` 之后它是 `None`，会抛 `AttributeError`。必须先判空
6. FormSet 的 `TOTAL_FORMS` 写成「减去删除数」→ **会静默丢级或跨级串行**（最坏的 bug）。`TOTAL_FORMS` 只增不减，删除靠勾 `DELETE` 隐藏域
7. `stage_order` 唯一性校验忘记排除 `deleted_forms` → 「删掉第 2 级同时新增一个第 2 级」会被误判为重复
8. 列表页忘记 `select_related` → N+1 查询
9. 忘记捕获 `ProtectedError` → 删被引用对象时 500
10. 删除走 GET 链接 → 必须 `DeleteView`（仅 POST）+ CSRF
11. 全局开 `USE_THOUSAND_SEPARATOR` → 会把 `type="number"` 的 UT 输入框值变成 `NaN`。**不要开**
12. 给 `ProgramLink` 写成一个对象可属于多个计划 → 与 5 条唯一约束冲突，设计是「最多属于一个计划」

---

## 11. 验证方式

```powershell
conda activate rocket
python manage.py makemigrations          # 首次迁移是数据模型的唯一权威验证
python manage.py migrate
python manage.py loaddata fixtures/bodies.json fixtures/parts_sample.json
python manage.py createsuperuser
python manage.py test                    # 必须全绿才算通过阶段 Gate
python manage.py runserver 127.0.0.1:8000
```

**必需的单测**（在 P0 就要建起来）：
- `services/orbital.py`：同步轨道自洽性（每个天体 `orbital_period(synchronous_sma(sidereal_day, mu), mu) ≈ sidereal_day`）、单级 Δv 手算、`apsis`、空值返回 `None`
- `services/deltav.py`：逐级 Δv 累加、起飞 TWR
- 表单：`SiteForm` 经纬度范围、`FlightLogForm` 状态-时间一致性、`Stage` 的 CHECK 真的拦得住越界写入

**断言用值**（已实测，直接用）：

| 用例 | 输入 | 期望 |
|---|---|---|
| Kerbin 同步轨道半长轴 | `mu=3.5316e12`, `sidereal_day=21549.4` | `a ≈ 3 463 331.36 m`（高度 ≈ 2 863.33 km） |
| 同步轨道回代周期 | `a=3463331.36`, `mu=3.5316e12` | `T ≈ 21549.4 s`（相对误差 < 1e-9） |
| 单级 Δv | `isp=345`, `m0=10 t`, `mf=4 t` | `3100.08 m/s` |
| 起飞 TWR | `thrust=200 kN × 4`, `m0=40 t`, `g=9.81` | `2.0387` |
| 近远拱点 | `sma=700000`, `e=0.1` | `(630 000, 770 000)` |
| Kerbin 100 km 低轨周期 | `sma=700000`, `mu=3.5316e12` | `1958.13 s`（**不是 1837 s** —— 那是 70 km 高度 `sma=670000` 的值） |

---

## 12. 设计存档

`docs/archive/` 保留设计阶段的全套过程文档（需求论证、技术选型对比、概念模型、旧系统债务清单等）。**开发不需要读它们。** 只在两种情况下去翻：

1. 想知道某个设计**为什么**这样定 → 看 `archive/_design-brief.md` 的决策记录 `D-01`~`D-23`
2. 需要旧系统的细节（如迁移原型数据）→ 看 `archive/07-重构方案与实施计划.md`

⚠️ `archive/07` 中引用的旧代码文件路径（`manage.py`、`forms.py`、`arock.sql` 等）**指向已归档的原型仓库 `OrionAstesia/rockets-manage`，不在本仓库**。
