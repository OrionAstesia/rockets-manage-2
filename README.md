# rockets-manage-2 · Kerbal 航天计划管理器

《坎巴拉太空计划》(Kerbal Space Program) 玩家的**发射计划与任务记录管理工具**。

> **状态**：设计阶段已完成（`docs/spec` 文档），**代码尚未开始**。开发时先阅读 `docs/spec/00-最小系统.md` 的起步。

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
| 框架 | **Django 5.2**（Admin 覆盖 11 张表的 CRUD） |
| 数据库 | **SQLite**（单文件 `db.sqlite3`，可直接拷贝备份） |
| Python | **3.10**，conda 环境名 **`rocket`** |
| 其他依赖 | **无**（不用 numpy、不用 DRF、不用 JS 库） |
| 前端 | Django 模板 + Bootstrap 5 + 原生 JS（**无构建链**） |
| 测试 | `manage.py test` |

---

## 仓库当前状态

⚠️ **这个仓库目前只有文档、依赖清单和种子数据，没有代码。**

**已存在**：

```
README.md              本文件
.gitignore
requirements.txt       唯一依赖 Django~=5.2.0
fixtures/bodies.json   6 个天体的种子数据（规格 §5.1）
docs/spec/00-最小系统.md   ★ 唯一权威源
docs/README.md
docs/archive/          设计过程存档，开发不需要读
```

**待创建**（按规格 §10 的 S1–S4 做）：`manage.py`、`config/`、5 个 app（`core` / `parts` / `fleet` / `spaceflight` / `ops`）、`templates/`、`services/orbital.py`。

所以下面的命令**在代码写出来之前会报错**，它们是目标状态、不是当前可用状态。

```powershell
# 0. 先按规格 §10 的 S1 创建项目骨架
django-admin startproject config .

# 1. 创建环境
#    ★ 本机已就绪：conda 环境 rocket 已存在（F:\Anaconda\envs\rocket，Python 3.10.21 + Django 5.2.17），无需重建
#    换机器时才需要下面三行：
conda create -n rocket python=3.10 -y
conda activate rocket
pip install -r requirements.txt

# 2. 初始化数据库
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata fixtures/bodies.json
python manage.py createsuperuser

# 3. 运行
python manage.py runserver 127.0.0.1:8000
```

- 应用界面 <http://127.0.0.1:8000/>
- 管理后台 <http://127.0.0.1:8000/admin/>

> ⚠️ **环境陷阱**：本机 PATH 上的 `python` 是 `D:\MinGW\bin\python.exe`（**无 Django**）。跑本项目**必须先 `conda activate rocket`**。另本机 `conda` 不在 PATH 中，可执行文件在 `F:\Anaconda\Scripts\conda.exe`——必要时用全路径或在 conda prompt 里操作。

---

## 文档

**只读这一份**：[`docs/spec/00-最小系统.md`](docs/spec/00-最小系统.md) —— 唯一权威源，11 张表 / 5 个 app / 7 个计算函数 / 3 个前台页面，一份文档讲完。

开发不需要读别的。`docs/archive/` 是设计过程存档（早期更庞大、已作废的设计），只在想知道「为什么这样定」时翻。

**边界**：无 JavaScript、无 AJAX、无多态外键、无 1:1 继承、无嵌套 FormSet、无新依赖（只要 Django）。写操作全部走 Django Admin，前台只负责看。

---

## 关于原型

本项目是 **`OrionAstesia/rockets-manage`**（Flask + MySQL 的火箭发射管理系统原型）的**重构继任者**。

- **原型仓库已归档，保持不动**，作为历史参考。它包含旧 Flask 代码（`manage.py` / `mysql_util.py` / `forms.py` / `arock.sql` / `templates/` 等）。
- **本仓库不包含旧代码**，是从文档重建的新实现（Django 5.2 + SQLite）。
- 设计决策的由来（为什么换技术栈、为什么废弃旧字段、为什么取消「族」表）见 `docs/archive/`。

---

## 三个最容易出错的地方

1. **`stage_order` 方向**：`1` = 最先点火的最下面一级（起飞级）；页面**降序**渲染（最上级在顶部），Δv **升序**累加（第 1 级的 `m₀` 要含上方所有级 + 载荷）。
2. **`sma` 不是高度**：高度 = `sma − Body.radius`（Kerbin 600 km）。混淆会产生 600 km 量级误差。
3. **Δv 用 `G0 = 9.80665` 常数，不用所在天体的重力**：用当地重力在 Kerbin 上只差 0.03%（测不出来），在 Mun 上差 83%。防护办法是 `stage_delta_v()` 的签名里不出现任何重力参数。

完整说明见 [`docs/spec/00-最小系统.md`](docs/spec/00-最小系统.md) §7。**注意：v1 里没有多态外键**（级直接挂火箭，航天计划用普通外键），所以「不用 `GenericForeignKey`」不再是本项目的注意事项。

---

## 遗留待裁决

无。**数据迁移路线已定为 A**：本仓库是全新实现，原型数据不迁移（规格 §11 明确「数据迁移脚本」不做）。

---

## 协议

仅供学习与个人使用。
