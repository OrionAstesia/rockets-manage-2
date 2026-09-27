# rockets-manage-2 · Kerbal 航天计划管理器

《坎巴拉太空计划》(Kerbal Space Program) 玩家的**发射计划与任务记录管理工具**。

> **状态**：v1 已实现（`docs/spec/00-最小系统.md` 的 S1–S4），并已完成「写操作从 Admin 移到前台」（`10-前台内联编辑改造.md`）、「左侧导航 + 每类数据独立成页」（`11-界面导航重构.md`）、**「增删改改弹窗 + 右下角悬浮新增按钮」**（`12-弹窗增删改.md`、`13-新增入口悬浮按钮.md`）。`manage.py test` **168 项全绿**。

---

## 这是什么

记录你在 KSP 里造过什么、打算发射什么、在轨有什么。它回答四个问题：

| 我想知道 | 系统提供 |
|---|---|
| 我造过哪些火箭和载荷？级是怎么配的？ | 部件库 + 火箭/载荷的**级结构**（级序、引擎、燃料罐） |
| 这枚火箭能不能把载荷送到目标轨道？ | **Δv 与推重比计算**（逐级累加） |
| 我接下来该发射什么？ | **发射日程**（尚未执行的任务按计划时间排列） |
| 我在轨有哪些资产？轨道和周期是多少？ | **在轨航天器**（轨道六要素 + 周期） |
| 这一堆东西是为了哪个存档在忙？ | **玩家存档**（1 个存档统辖 n 个火箭/载荷/发射/发射场/航天器） |

---

## 技术栈

| 项 | 选择 |
|---|---|
| 框架 | **Django 5.2**（前台页面负责增删改；Admin 保留作兜底，不放入口） |
| 数据库 | **SQLite**（单文件 `db.sqlite3`，可直接拷贝备份） |
| Python | **3.10**，conda 环境名 **`rocket`** |
| 其他依赖 | **无**（不用 numpy、不用 DRF、不用 JS 库） |
| 前端 | Django 模板 + Bootstrap 5（CDN）＋**一个 30 行的原生 JS**（`static/js/modal.js`，只负责开关原生 `<dialog>`；无 AJAX、无前端校验、无 JS 库） |
| 测试 | `manage.py test` |

---

## 仓库当前状态

✅ **功能与界面改造都已完成，可以跑了。**

```
manage.py
config/                  settings（zh-hans / Asia-Shanghai / 根 templates / STATICFILES_DIRS）+ urls
core/                    Body 模型、constants.py（常量）、forms.py（表单基类 + program 注入）、
                         views.py（DialogCrudMixin + SaveScopedCrudView + CrudListView + 主页 + 存档列表）
parts/                   三种部件模型 + 表单 + /reference/<四类>/ 列表页（带弹窗）
fleet/                   Rocket / RocketStage / Payload + 表单 + 火箭详情（级序 + Δv + 级的弹窗）
spaceflight/             Site / Spacecraft 模型与表单（没有自己的 URL，页面在 ops 里）
ops/                     Save / FlightLog + 表单 + /saves/<pk>/<五类>/ 列表页（带弹窗）+ /schedule/
services/orbital.py      7 个纯计算函数（周期 / 拱点 / 高度 / 逐级 Δv）
static/js/modal.js       唯一的 JS：开关弹窗、点遮罩关闭、校验失败后自动重开
templates/
  base.html              左侧主导航 + {% block subnav %} + messages + 右下角悬浮「+」按钮
  includes/_dialog.html  通用弹窗骨架（所有增删改弹窗都用它）
  core/home.html         空主页（占位）
  core/save_list.html    存档列表 /saves/（存档的增删改弹窗）
  ops/save_base.html     存档二级导航骨架
  ops/save_{rockets,payloads,sites,spacecraft,flights}.html   每个集合一页 + 弹窗
  ops/schedule.html      发射日程（只读）
  fleet/rocket_detail.html   火箭详情 + 级的弹窗增删改
  parts/reference_base.html  参考数据二级导航骨架
  parts/{engine,fueltank,instrument,body}_list.html          每类一页（天体只读）
fixtures/bodies.json     6 个天体的种子数据（规格 §5.1），已随仓库提供
docs/spec/00-最小系统.md           数据模型 / 计算 / 种子数据（权威）
docs/spec/10-前台内联编辑改造.md    前台可写（权威）
docs/spec/11-界面导航重构.md        导航结构与页面拆分（权威）
docs/spec/12-弹窗增删改.md          弹窗增删改 + 单端点 POST 协议（权威）
docs/spec/13-新增入口悬浮按钮.md    右下角悬浮「+」按钮（权威）
README.md  requirements.txt  .gitignore
```

## 怎么跑

```powershell
# 1. 环境
#    ★ 本机已就绪：conda 环境 rocket 已存在（F:\Anaconda\envs\rocket，Python 3.10.21 + Django 5.2.17），无需重建
#    换机器时才需要下面三行：
conda create -n rocket python=3.10 -y
conda activate rocket
pip install -r requirements.txt

# 2. 初始化数据库（已有 db.sqlite3 可跳过）
python manage.py migrate
python manage.py loaddata fixtures/bodies.json
python manage.py createsuperuser        # 只在想用 /admin/ 兜底时才需要

# 3. 运行与自测
python manage.py test                   # 85 项，应全绿
python manage.py runserver 127.0.0.1:8000
```

- 应用界面 <http://127.0.0.1:8000/>（**增删改都在前台**，不需要登录）
- 管理后台 <http://127.0.0.1:8000/admin/>（保留作兜底，前台导航里没有入口）

> 第一次使用：`/` 首页直接新建一个**存档** → 进 `/saves/<pk>/` 工作台 → 到 `/reference/` 录引擎与燃料罐 → 回工作台录火箭（级在火箭详情页里加）、发射场、航天器、发射日志。

> ⚠️ **环境陷阱**：本机 PATH 上的 `python` 是 `D:\MinGW\bin\python.exe`（**无 Django**）。跑本项目**必须先 `conda activate rocket`**，或直接用 `F:\Anaconda\envs\rocket\python.exe manage.py ...`。另本机 `conda` 不在 PATH 中，可执行文件在 `F:\Anaconda\Scripts\conda.exe`。

---

## 页面一览

导航是**左侧栏**，只有三大模块（存档 / 参考数据 / 发射日程）；存档与参考数据各有一层**二级导航**，每类数据独立成页（一页一张表）。

**增删改没有独立路由**：每条列表页自己就是端点，右下角的悬浮「+」开新建弹窗、行尾按钮开编辑/删除弹窗，表单 POST 回同一条 URL，用隐藏字段 `action`（`create`/`update`/`delete`）分流。

| 页面 | 路径 | 作用 |
|---|---|---|
| 主页（暂空） | `/` | 占位文案；只能从侧栏顶部的应用名进入，不在侧栏项里 |
| 存档列表 | `/saves/` | 全部存档 + 全局统计 + 近期发射；存档的增删改弹窗 |
| 存档各集合 | `/saves/<pk>/{rockets,payloads,sites,spacecraft,flights}/` | 五类数据各一页 + 弹窗增删改（二级导航切换） |
| 火箭详情 | `/rockets/<pk>/` | 火箭属性 + 级序列表（降序）+ 逐级 Δv + 总 Δv；级的增删改弹窗 |
| 参考数据 | `/reference/{engines,fueltanks,instruments,bodies}/` | 三类部件弹窗增删改；天体只读（无悬浮按钮） |
| 旧参考数据入口 | `/reference/` | 302 → `/reference/engines/`（只为旧书签不 404） |
| 发射日程 | `/schedule/` | 全存档的待发任务（跨存档，只读） |

---

## 文档

- [`docs/spec/00-最小系统.md`](docs/spec/00-最小系统.md) —— **数据模型 / 计算 / 种子数据**的权威源（11 张表 / 5 个 app / 7 个计算函数）。
- [`docs/spec/10-前台内联编辑改造.md`](docs/spec/10-前台内联编辑改造.md) —— **前台可写**的权威源（`00` 里「前台只读、写操作全在 Admin」的说法已作废）。
- [`docs/spec/11-界面导航重构.md`](docs/spec/11-界面导航重构.md) —— **导航结构与页面拆分**的权威源（左侧栏、二级导航、每类数据独立成页、`/` 与 `/saves/` 的分工）。
- [`docs/spec/12-弹窗增删改.md`](docs/spec/12-弹窗增删改.md) —— **弹窗增删改与单端点 POST 协议**的权威源（删掉 31 条 CRUD 路由，引入唯一的 JS 文件）。
- [`docs/spec/13-新增入口悬浮按钮.md`](docs/spec/13-新增入口悬浮按钮.md) —— **右下角悬浮「+」按钮**的权威源（哪个页面有、哪个没有、文案同步）。

`docs/archive/` 是设计过程存档（早期更庞大、已作废的设计），只在想知道「为什么这样定」时翻。

**边界**：无 AJAX（JS 只管开关弹窗，数据仍走浏览器原生表单 POST）、无前端校验（校验全在服务端，错误回显到弹窗）、无多态外键、无 1:1 继承、无嵌套 FormSet、无 JS 库、无新 Python 依赖（只要 Django）。

---

## 关于原型

本项目是 **`OrionAstesia/rockets-manage`**（Flask + MySQL 的火箭发射管理系统原型）的**重构继任者**。

- **原型仓库已归档，保持不动**，作为历史参考。它包含旧 Flask 代码（`manage.py` / `mysql_util.py` / `forms.py` / `arock.sql` / `templates/` 等）。
- **本仓库不包含旧代码**，是从文档重建的新实现（Django 5.2 + SQLite）。
- 设计决策的由来（为什么换技术栈、为什么废弃旧字段、为什么取消「族」表）见 `docs/archive/`。

---

## 六个最容易出错的地方

1. **`stage_order` 方向**：`1` = 最先点火的最下面一级（起飞级）；页面**降序**渲染（最上级在顶部），Δv **升序**累加（第 1 级的 `m₀` 要含上方所有级 + 载荷）。质量闭合要用 `vehicle_delta_v(...)[0]`（起飞级），不是 `[-1]`。
2. **`sma` 不是高度**：高度 = `sma − Body.radius`（Kerbin 600 km）。混淆会产生 600 km 量级误差。
3. **Δv 用 `G0 = 9.80665` 常数，不用所在天体的重力**：用当地重力在 Kerbin 上只差 0.03%（测不出来），在 Mun 上差 83%。防护办法是 `stage_delta_v()` 的签名里不出现任何重力参数。
4. **存档外键叫 `program`，不能叫 `save`**：`save` 与 Django 的 `Model.save()` 同名，会遮蔽方法，让 `objects.create()` / Admin 保存直接抛 `TypeError: 'Save' object is not callable`（`manage.py check` 和 `makemigrations` 都查不出来）。
5. **删存档要先清航天器与发射日志**：`FlightLog` 以 `PROTECT` 引用火箭/载荷/发射场，直接删存档会被 Django 拒绝。顺序写在 `ops.Save.delete()`，前台删除页另有 `get_deleted_objects()` 配套（Admin 侧同理）。
6. **`program` 必须从 URL/实例取，不能做成隐藏字段**：否则改一下 URL 就能把火箭写进别人的存档。表单里干脆不出现该字段（`core.forms.ProgramScopedFormMixin`）。

完整说明见 [`docs/spec/00-最小系统.md`](docs/spec/00-最小系统.md) §4.6 / §4.11 / §7 与 [`docs/spec/10-前台内联编辑改造.md`](docs/spec/10-前台内联编辑改造.md) §5。**注意：v1 里没有多态外键**（级直接挂火箭，火箭/载荷等用普通外键归属存档），所以「不用 `GenericForeignKey`」不再是本项目的注意事项。

---

## 遗留待裁决

无。**数据迁移路线已定为 A**：本仓库是全新实现，原型数据不迁移（规格 §11 明确「数据迁移脚本」不做）。

---

## 协议

仅供学习与个人使用。
