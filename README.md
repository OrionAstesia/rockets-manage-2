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
3. **多态 FK 不用 `GenericForeignKey`**：`Stage` 与 `ProgramLink` 用 `owner_type` + 可空 FK + CHECK；否则无法建立数据库级外键与约束。

完整说明见 [`docs/spec/01-架构与开发指南.md`](docs/spec/01-架构与开发指南.md) §5。

---

## 遗留待裁决

| 问题 | 位置 |
|---|---|
| **数据迁移路线 A/B/C**：本仓库是全新实现，**原型数据默认不迁移**（路线 A）。若日后想保留原型里那 5 枚含 KSP 级配置文本的火箭，走路线 C（只迁 `arock.sql` 的 17 行） | 基准 §11.4 ｜ `07` §8 |

---

## 协议

仅供学习与个人使用。
