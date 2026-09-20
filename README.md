# rockets-manage-2 · Kerbal 航天计划管理器

《坎巴拉太空计划》(Kerbal Space Program) 玩家的**发射计划与任务记录管理工具**。

> **状态**：设计阶段已完成（`docs/` 全套文档），**代码尚未开始**。开发从 `docs/08-任务清单.md` 的 **P0 地基** 起步。

---

## 这是什么

记录你在 KSP 里造过什么、打算发射什么、在轨有什么。它回答四个问题：

| 我想知道 | 系统提供 |
|---|---|
| 我造过哪些火箭和载荷？级是怎么配的？ | 部件库 + 火箭/载荷的**级结构**（级序、引擎、燃料罐） |
| 这枚火箭能不能把载荷送到目标轨道？ | **Δv 与推重比计算**（逐级累加） |
| 我接下来该发射什么？ | **发射日程**（尚未执行的任务按计划时间排列） |
| 我在轨有哪些资产？轨道和周期是多少？ | **在轨航天器**（轨道六要素 + 周期） |
| 这一堆东西是为了哪个目标在忙？ | **航天计划**（1 个计划统辖 n 个火箭/载荷/发射/发射场/航天器） |

---

## 技术栈

| 项 | 选择 |
|---|---|
| 框架 | **Django 5.2**（Admin 覆盖 14 张表的 CRUD） |
| 数据库 | **SQLite**（单文件 `db.sqlite3`，可直接拷贝备份） |
| Python | **3.10**，conda 环境名 **`rocket`** |
| 计算 | `numpy` |
| 前端 | Django 模板 + Bootstrap 5 + 原生 JS（**无构建链**） |
| 测试 | `manage.py test` |

---

## 快速开始

```powershell
# 1. 创建环境（本机 PATH 上的 python 是 D:\MinGW\bin\python.exe，没有 Django，务必用 conda 环境）
conda create -n rocket python=3.10 -y
conda activate rocket
pip install -r requirements.txt

# 2. 初始化数据库
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata fixtures/bodies.json fixtures/parts_sample.json
python manage.py createsuperuser

# 3. 运行
python manage.py runserver 127.0.0.1:8000
```

- 应用界面 <http://127.0.0.1:8000/>
- 管理后台 <http://127.0.0.1:8000/admin/>

> ⚠️ **环境陷阱**：本机 PATH 上的 `python` 是 `D:\MinGW\bin\python.exe`（**无 Django**）。跑本项目**必须先 `conda activate rocket`**。另本机 `conda` 不在 PATH 中，可执行文件在 `F:\Anaconda\Scripts\conda.exe`——必要时用全路径或在 conda prompt 里操作。

---

## 文档（唯一权威源）

**改任何设计前先读 [`docs/_design-brief.md`](docs/_design-brief.md)**——它是全部文档的基准。

| 文件 | 内容 |
|---|---|
| [`docs/README.md`](docs/README.md) | 文档中心与阅读顺序 |
| [`docs/_design-brief.md`](docs/_design-brief.md) | **内部基准**：决策 D-01~D-23、14 张表字段定义、枚举、KSP 常数、路由表、修订日志 |
| [`docs/01-需求规格说明.md`](docs/01-需求规格说明.md) | 技术选型论证、51 条功能需求、47 条非功能需求、用例、范围声明 |
| [`docs/02-概念模型.md`](docs/02-概念模型.md) | KSP 术语↔模型映射、ER 图、实体关系与基数 |
| [`docs/03-数据库设计.md`](docs/03-数据库设计.md) | **数据模型冻结于此**：Django 模型代码、数据字典、约束与索引 |
| [`docs/04-接口与路由设计.md`](docs/04-接口与路由设计.md) | 50 条路由、视图规范、表单与 FormSet、services 契约、安全设计 |
| [`docs/05-页面交互设计.md`](docs/05-页面交互设计.md) | 34 个页面的布局与交互、级 FormSet 动态增删、计算值展示规范 |
| [`docs/06-核心计算设计.md`](docs/06-核心计算设计.md) | 火箭方程、推重比、轨道周期、近远拱点、霍曼转移、简化登记、测试断言 |
| [`docs/07-重构方案与实施计划.md`](docs/07-重构方案与实施计划.md) | 设计决策由来、数据迁移路线、P0–P4 实施计划、风险与回滚 |
| [`docs/08-任务清单.md`](docs/08-任务清单.md) | **可勾选 WBS**：171 项任务，从这里开始干活 |
| [`docs/09-新仓库启动说明.md`](docs/09-新仓库启动说明.md) | 本仓库的来历、与已归档原型的关系、开工前须知 |

---

## 关于原型

本项目是 **`OrionAstesia/rockets-manage`**（Flask + MySQL 的火箭发射管理系统原型）的**重构继任者**。

- **原型仓库已归档，保持不动**，作为历史参考。它包含旧 Flask 代码（`manage.py` / `mysql_util.py` / `forms.py` / `arock.sql` / `templates/` 等）。
- **本仓库不包含旧代码**，是从文档重建的新实现（Django 5.2 + SQLite）。
- 设计决策的由来（为什么换技术栈、为什么废弃旧字段、为什么取消「族」表）记录在 [`docs/01`](docs/01-需求规格说明.md) 与 [`docs/07`](docs/07-重构方案与实施计划.md)。**注意 `07` 中描述旧代码的文件路径与行号时，指的是已归档的原型仓库，不在本仓库内。**

---

## 关键约定（动手前务必知道）

### 术语
本项目的「**级间段**」指**火箭的级（stage）**，不是 interstage/decoupler 分离环零件。

### 级序方向（最易出错）
- `stage_order = 1` = **最先点火、位于最下方的那一级**（起飞级），向上递增。
- 页面按 `stage_order` **降序自上而下**渲染（最上级在顶部，与火箭外观一致）。
- Δv 从 `stage_order = 1` 起**升序**累加（算第 1 级时要把**上方所有级 + 载荷**质量计入 `m₀`）。
- `sma`（轨道半长轴）**不等于高度**，两者相差 `Body.radius`（Kerbin 为 600 km）——这是本项目计算层最易出错处。

### 编号体系（**新增编号前先 grep 全 `docs/`**）
| 编号 | 含义 |
|---|---|
| `M1/M2/M3` | **实施里程碑**（见 `08`） |
| `R-01`~`R-10` | **风险编号**（见 `08`） |
| **路线 A/B/C** | **数据迁移路线**（见基准 §11.4） |
| `D-01`~`D-23` | 设计决策（见基准） |

> 基准初稿曾先后用 `M1/M2/M3` 与 `R1/R2/R3` 命名迁移路线，两次都与 `08` 的既有编号撞车——新增编号体系前务必先检查。

---

## 遗留待裁决

| 问题 | 位置 |
|---|---|
| **数据迁移路线 A/B/C**：本仓库是全新实现，**原型数据默认不迁移**（路线 A）。若日后想保留原型里那 5 枚含 KSP 级配置文本的火箭，走路线 C（只迁 `arock.sql` 的 17 行） | 基准 §11.4 ｜ `07` §8 |

---

## 协议

仅供学习与个人使用。
