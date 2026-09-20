# 设计基准（Design Brief）— rocket_manage 重构

> **文档性质**：内部基准文档，**唯一权威源（Single Source of Truth）**。
> `00`–`08` 各份交付文档中的字段名、类型、枚举值、表名、路由、常数，一律以本文为准；若某份文档与本文冲突，以本文为准并回改该文档。
>
> **读者**：本项目的开发过程（含 AI 协作者）。玩家用户阅读 `docs/README.md` 即可，不需要读本文。
>
> **版本**：v1.0 ｜ 定稿日期：2026-09-19 ｜ 状态：已确认

---

## 0. 项目定位与决策记录

### 0.1 定位
《坎巴拉太空计划》（Kerbal Space Program，KSP）玩家的**发射计划与任务记录管理工具**。单机、自用、单人。

核心诉求（按优先级）：
1. **记录**：玩家建造的火箭、载荷、发射场、部件，以及每一次发射日志。
2. **安排**：把「计划要发射但还没发射」的任务排进日程，与已完成的发射区分开。
3. **统筹**：用「航天计划」把多个火箭/载荷/发射/在轨航天器归到一个目标下，方便看整体进度。
4. **在轨管理**：记录正在运行的航天器及其轨道参数。

### 0.2 已确认的决策（决策记录 / Decision Log）

| 编号 | 决策项 | 结论 | 理由摘要 |
|---|---|---|---|
| D-01 | 项目定位 | **自用工具** | 你是 KSP 玩家，真要拿它安排发射计划；选型以「多久能用上 + 改需求多痛」为准 |
| D-02 | 技术栈 | **Django 5.2 + SQLite** | Django Admin 白送 14 张表的 CRUD，砍掉约 70% 工作量；SQLite 单文件可拷贝备份，符合游戏记录本形态 |
| D-03 | 数据库 | **SQLite**（`db.sqlite3`） | 换 MySQL 8.4 在 Django 下约 1 小时，但数据迁移需 `dumpdata`/`loaddata`；v1 不做 |
| D-04 | Python 环境 | **新建 conda 环境 `rocket`，Python 3.10** | 不污染服务 RAG 项目的 `rag` 环境；`OrionDB` 环境是 3.9 且无 sqlalchemy，需替换 |
| D-05 | 主键策略 | **`id` INT 自增（Django 默认） + 独立业务短码 `code`** | 消灭旧 `CHAR(5)` 编号耗尽问题；`code` 供玩家阅读 |
| D-06 | 航天计划 1:n | **`ProgramLink` 链接表 + 可空 FK + CHECK 恰好一个非空** | 真 1:n、外键完整、加新对象类型不动老表 |
| D-07 | 「级间段」语义 | **= 火箭的「级」（stage）**，非 interstage/decoupler 零件 | 你的原话「1 级有 n 燃料罐或引擎」表明此意 |
| D-08 | 族—型号两层 | **全部取消**（`EngineFamily`/`StageFamily`/`CarrierFamily`/`PayloadFamily`） | 见第 2 节论证：族只携带「名称+描述」，n 端无可共享实质属性，属可消除的传递依赖 |
| D-09 | v1 范围 | 只做 6 项新增需求，**排除**乘员 kerbal 表、多用户权限、导入导出 | 你最聚焦的选择 |
| D-10 | `Body` 天体表 | **保留** | KSP 语义必需：`Site.body`、`Spacecraft.body` 要用，且没有 `Body.mu` 就算不出轨道周期 |
| D-11 | 交付物 | 8 份交付文档 + 本基准文档 | 本轮只产出文档，不写任何 Django 代码 |
| D-12 | 轨道周期存储 | `sma`（半长轴）为唯一权威输入，周期为派生值 + 可选快照 `cached_period_sec` | 见第 8.3 节论证 |
| D-13 | 前端 | Django 模板 + Bootstrap 5 + 原生 JS（无构建链） | 动态级表单用 JS 克隆表格行 |

### 0.3 v1 明确排除（列入后续扩展）
- 乘员 Kerbal 名册与乘员-航天器分配（仅在 `FlightLog.crew_count` / `Spacecraft.crew_count` 记人数）
- 多用户与角色权限（沿用 Django 内置认证，单玩家）
- 数据导入导出、KSP 存档解析（`.sfs` 文件）
- 整流罩/分离环/电池/太阳能板等 `PartCatalog.part_type=OTHER` 之外的结构件细分建模
- 部件级质量/推力的自动计算器（v1 只做展示与简单汇总）

---

## 1. 术语映射表（KSP ↔ 数据模型）

> 本表是 `02-概念模型` 的基础，也是文档与界面用词的统一依据。

| KSP 中文惯用 | KSP 英文 | 表/字段 | 说明 |
|---|---|---|---|
| 部件 / 零件 | Part | `PartCatalog` | 所有部件的公共属性（名称/直径/干重/造价/科技节点） |
| 燃料罐 | Fuel Tank | `FuelTank`（1:1 `PartCatalog`） | 容量、燃料类型、湿重 |
| 引擎 | Engine | `Engine`（1:1 `PartCatalog`） | 推力、比冲、万向节、节流范围 |
| 科学设备 / 实验装置 | Science Instrument | `ScienceInstrument`（1:1 `PartCatalog`） | 实验类型、数据量、是否可重复 |
| 级 / 级间段 | Stage | `Stage` | **本项目的「级间段」即指此**。有序、含引擎与燃料罐 |
| 级-燃料罐挂载 | — | `StageTank` | 一级挂 n 个燃料罐 |
| 运载火箭 | Launch Vehicle / Rocket | `CarrierModel` | 玩家建造的火箭型号 |
| 有效载荷 | Payload | `PayloadModel` | 舱段/卫星/探测器/着陆器 |
| 发射场 | Launch Site | `Site` | 含天体归属与发射台等级 |
| 天体 | Celestial Body | `Body` | 自引用树（Kerbin → Mun），带 `mu` |
| 发射日志 / 任务记录 | Launch / Flight Log | `FlightLog` | **替代旧 `SCP` 表**；含计划与实发时间 |
| 航天计划 | Space Program | `Program` | 1:n 的「1」端 |
| 计划成员 | — | `ProgramLink` | 1:n 的「n」端，多态挂接 |
| 在轨航天器 | Active Vessel / Spacecraft | `Spacecraft` | 轨道六要素 + 周期 |
| 半长轴 | Semi-major Axis | `Spacecraft.sma` | 周期的唯一权威输入 |
| 近拱点 / 远拱点 | Periapsis / Apoapsis | 派生字段 | 由 `sma` + `eccentricity` 计算，**不落库** |
| 比冲 | Specific Impulse | `Engine.isp_asl` / `isp_vac` | 单位秒 |
| 标准重力加速度 | Standard Gravity | `G0 = 9.80665` | 常数，见第 9 节 |
| 标准重力参数 | Standard Gravitational Parameter | `Body.mu` | 单位 m³/s²，周期计算必需 |
| 影响球 | Sphere of Influence | `Body.soi_radius` | 单位 m |
| 序列 / 系列 | Series | `*.series` | 分组用，**替代已取消的「族」表** |
| 变体来源 | Derived From | `*.derived_from` | 自引用 FK，记录改自哪个型号 |

---

## 2. 「族」被取消的论证（决策 D-08 的完整依据）

### 2.1 参考项目 `ek` 的实际数据形态
`F:\Codes\DownloadProjects\ek\ek.py:13`：

```python
class EngineFamily(object):
    def __init__(self, name, description, vac=False):
        self.name = name
        self.description = description
        self.vac = vac
```

`ek.py:34-49` 的 `Engine.description` / `Engine.vac` 属性在自身值为 `None` 时**回退到 family 的默认值**。即族只提供「一句描述」与「是否真空版」两个可继承默认值。

`sample.py` 中 10 个引擎族的成员分布：`AJ10`(7) / `XLR81`(5) / `LR79`(4) / `LR105`(4) / `RL10`(3) / `Aerobee`(2) / `H1Family`(2) / `Redstone`(1) / `Castor`(1) / `J2`(1)。

以 `AJ10` 为例，其 7 个成员（`AJ10-27`/`-37`/`-42`/`-101A`/`-104`/`-138`/`-142`）**共享的只有那句描述与 `vac=True`**；推力、比冲、质量、造价全部在各自的 `Engine` 行上，一个都没有共享。

### 2.2 判定标准（3NF 传递依赖）
> 若族表只携带「名称 + 描述」，而描述又是可继承的默认值，则它把一个属性从 n 端抽出单独存放，属于**可消除的传递依赖**，不应独立成表。
>
> 族表值得独立存在的唯一条件：**它携带 n 端无法共享、且非派生、且写入时会重复的实质性属性。**

### 2.3 逐族判定

| 族 | n 端成员 | 族携带的实质共享属性 | 判定 |
|---|---|---|---|
| `EngineFamily` | 10 族，最多 7 成员 | 无 | ❌ 取消 |
| `StageFamily` | `Able`→4、`Delta`→4 | `engine` + `engine_count` 默认值 | ❌ 取消（这正是 `Stage` 本身） |
| `CarrierFamily` | `Davy 2`/`2A`/`2B` | 无（原本只打算放 `description`） | ❌ 取消 |
| `PayloadFamily` | 同上 | 无 | ❌ 取消 |

`ek` 需要族层级的两个原因，均不适用于本项目：
1. 数据是 Python 字面量，`LV("Davy 2", Davy2Family, ...)` 写法能少打字 — **静态代码里的复用诉求**。
2. 族是**报告分组**层级（`Database.update()` 构建 `lv_family_tree`/`engine_family_tree`）— **库里一列 `series` 加 `GROUP BY` 即可，无需建表**。

### 2.4 替换方案
在每个子表加两个字段，把「分组」与「血缘」降级为属性：

| 字段 | 类型 | 作用 |
|---|---|---|
| `series` | `VARCHAR(60)`，可空 | 分组/筛选用（`AJ10`、`XLR81`、`Davy 2x`）。可空 = 不强制分类 |
| `derived_from` | 自引用 `FK(self)`，可空 | 变体血缘（`Davy 2B.derived_from = Davy 2`），比 `ek` 的扁平族**信息更丰富** |

「火箭族」概念未丢失：`CarrierModel.objects.filter(series="Davy 2x")` 即族视图，`GROUP BY series` 即族统计。收益：少一张表、少一个 JOIN、少一层级联删除、录入少一步。

### 2.5 `PartCatalog` 为何**保留**（与「族」性质不同）
`PartCatalog` 携带**所有部件类型真正共享的属性**：`name` / `diameter` / `dry_mass` / `cost` / `tech_node` / `manufacturer`。燃料罐、引擎、科学设备的**每一行都真的有这些值**，是货真价实的 1:1 超类（消除多值依赖），不是可消除的传递依赖。故保留，但 `Engine.family` 之类的 FK 已去除。

---

## 3. 实体清单（14 张表，9 个 app）

| # | app | 模型 | 中文名 | 旧表对照 |
|---|---|---|---|---|
| 1 | `core` | `Body` | 天体 | **新增** |
| 2 | `parts` | `PartCatalog` | 部件目录 | **新增** |
| 3 | `parts` | `FuelTank` | 燃料罐 | **新增**（需求①） |
| 4 | `parts` | `Engine` | 引擎 | **新增**（需求②） |
| 5 | `parts` | `ScienceInstrument` | 科学设备 | **新增**（需求③） |
| 6 | `carriers` | `CarrierModel` | 运载火箭型号 | ← `Carrier`（改造） |
| 7 | `payloads` | `PayloadModel` | 有效载荷型号 | ← `Payload`（改造） |
| 8 | `stages` | `Stage` | 级 | **新增**（需求⑥） |
| 9 | `stages` | `StageTank` | 级-燃料罐挂载 | **新增**（需求⑥） |
| 10 | `sites` | `Site` | 发射场 | ← `Site`（改造） |
| 11 | `launches` | `FlightLog` | 发射日志 | ← `SCP`（改名改造；**旧表注释本就写「建立"发射日志"表SCP"**） |
| 12 | `programs` | `Program` | 航天计划 | **新增**（需求⑤） |
| 13 | `programs` | `ProgramLink` | 计划成员链接 | **新增**（需求⑤） |
| 14 | `spacecraft` | `Spacecraft` | 在轨航天器 | **新增**（需求④） |

另有 Django 内置 `auth.User`（`users` 语义由 `auth_user` 提供），不新增自定义用户表。

**6 项新增需求覆盖情况**：
① 燃料罐表 → `FuelTank` ｜ ② 引擎表 → `Engine` ｜ ③ 科学设备表 → `ScienceInstrument` ｜ ④ 在轨航天器 → `Spacecraft` ｜ ⑤ 航天计划 1:n → `Program` + `ProgramLink` ｜ ⑥ 火箭/载荷的级结构 → `Stage` + `StageTank`

---

## 4. 字段级定义（权威）

### 4.0 全局约定

| 项 | 约定 |
|---|---|
| 表名 | Django 默认 `app_label_ModelName` 小写，如 `parts_fueltank`。**旧文档中出现的 `abc_Model` 形式即为实际表名** |
| 命名风格 | Python 字段 `snake_case`；类名 `PascalCase`；所有字段带 `verbose_name`（中文标签）与必要 `help_text` |
| 中文注释 | 每个模型的 `Meta.verbose_name` / `verbose_name_plural` 必须是中文 |
| 主键 | 统一 `id = BigAutoField`（Django 默认）；业务短码列 `code` 独立唯一 |
| `code` 规范 | `VARCHAR(24)`，`unique=True`，`db_index=True`；格式见第 4.14 节 |
| 时间 | **KSP 游戏时间 `UT`**（游戏内秒，FloatField）。不存现实世界时间，不使用 `DateField`/`DateTimeField` |
| 质量 | **吨（t）**，`FloatField`。KSP 惯用单位 |
| 推力 | **千牛（kN）**，`FloatField` |
| 比冲 | **秒（s）**，`FloatField` |
| 距离 | **米（m）**，`FloatField`（KSP 轨道参数惯用米） |
| 角度 | **度（°）**，`FloatField`，范围 0–360（倾角 0–180） |
| 造价 | **根币（√）**，`PositiveIntegerField` |
| 软删除 | v1 不使用；删除策略见 4.15 |
| 审计字段 | 除 `Body`/`PartCatalog` 外，主要业务表加 `created_at` / `updated_at`（`auto_now_add` / `auto_now`，**现实世界时间**，用于管理而非数据语义） |
| **模型基类** | 所有含 `code` 字段的模型（含 `FlightLog`、`FuelTank`、`Engine`、`ScienceInstrument`）**一律继承 `core.mixins.CodeModel`**（提供 `code` 字段 + 正则校验 + `clean()`）；需要时间戳的另继承 `TimeStampedModel`。**共 11 张表带 `code`**：`Body`/`PartCatalog`/`FuelTank`/`Engine`/`ScienceInstrument`/`CarrierModel`/`PayloadModel`/`Site`/`FlightLog`/`Program`/`Spacecraft` |

### 4.1 `core.Body` — 天体

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 天体代号 |
| `name` | CharField(60) | unique | 天体名称 |
| `name_en` | CharField(60) | blank | 英文名 |
| `parent` | FK(self) | null, blank, on_delete=PROTECT, related_name='children' | 母天体 |
| `radius` | FloatField | null, blank | 赤道半径 (m) |
| `mu` | FloatField | null, blank | 标准重力参数 (m³/s²) |
| `soi_radius` | FloatField | null, blank | 影响球半径 (m) |
| `atmosphere_height` | FloatField | default=0 | 大气高度 (m) |
| `has_atmosphere` | BooleanField | default=False | 有大气 |
| `sidereal_day` | FloatField | null, blank | 恒星日 (s) |
| `solar_day` | FloatField | null, blank | 太阳日 (s) |
| `surface_gravity` | FloatField | null, blank | 表面重力 (m/s²) |
| `is_star` | BooleanField | default=False | 是恒星（Kerbol） |
| `is_reachable` | BooleanField | default=True | 可达（KSP 原版无其他星系） |
| `sort_order` | PositiveIntegerField | default=0 | 显示排序 |
| `description` | TextField | blank | 备注 |

**自引用树**：对应 `ek.Destination` 的 `category` 递归结构。`Meta.ordering = ['sort_order', 'name']`；层级缩进用**计算属性** `Body.depth`（沿 `parent` 链求深度，不落库）；层级查询用递归 CTE（**注意：SQLite 对 `WITH RECURSIVE` 支持有限，v1 允许在 Python 侧遍历 `parent` 链**，天体仅 17 条，性能无虞）。

**约束**：`CheckConstraint(condition=Q(parent__isnull=True) | ~Q(parent_id=F('id')), name='body_no_self_parent')`（禁止自己当自己的母天体）。

### 4.2 `parts.PartCatalog` — 部件目录

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 部件代号 |
| `name` | CharField(80) | unique | 部件名称 |
| `part_type` | CharField(12) | choices=`PartType`, db_index | 部件类型 |
| `manufacturer` | CharField(60) | blank | 制造商 |
| `diameter` | FloatField | null, blank | 直径 (m) |
| `dry_mass` | FloatField | default=0 | 干重 (t) |
| `cost` | PositiveIntegerField | default=0 | 造价 (√) |
| `tech_node` | CharField(60) | blank | 所属科技节点 |
| `allow_fuel_crossfeed` | BooleanField | default=False | 允许燃料交叉供给 |
| `is_radial` | BooleanField | default=False | 径向安装件 |
| `stackable` | BooleanField | default=True | 可堆叠 |
| `description` | TextField | blank | 说明 |

**`PartType` 枚举**：`TANK`(燃料罐) / `ENGINE`(引擎) / `SCIENCE`(科学设备) / `OTHER`(其他结构件)

**索引**：`Index(fields=['part_type', 'diameter'])`（按类型+直径筛选适配性）

**说明**：`is_radial`/`stackable` 保留在 `PartCatalog` 而非各子表——它们是所有部件类型的安装共性，属超类属性。

### 4.3 `parts.FuelTank` — 燃料罐（需求①）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `part` | OneToOneField(PartCatalog) | on_delete=CASCADE, related_name='fuel_tank' | 对应部件 |
| `wet_mass` | FloatField | — | 满载质量 (t) |
| `capacity` | FloatField | — | 燃料容量 (单位) |
| `fuel_type` | CharField(12) | choices=`FuelType` | 燃料类型 |
| `usable_capacity` | FloatField | null, blank | 可用容量 (单位) |
| `is_jet` | BooleanField | default=False | 喷气燃料罐 |
| `note` | TextField | blank | 备注 |

**`FuelType` 枚举**：`LF_OX`(液体燃料+氧化剂) / `MONO`(单元推进剂) / `XENON`(氙气) / `SOLID`(固体燃料) / `ORE`(矿石) / `OTHER`(其他)

**约束**：
- `CheckConstraint(condition=Q(capacity__gte=0), name='fueltank_capacity_nonneg')`
- `CheckConstraint(condition=Q(wet_mass__gte=F('part__dry_mass')), ...)` — **不可行**（跨表 CHECK 在 SQLite/SQLAlchemy ORM 层无 FK 子查询支持），改为**模型 `clean()` 校验**：`wet_mass >= part.dry_mass`，在 Django 表单与 `full_clean()` 中生效。

**⚠️ 容量语义（必须写进 `06` 文档）**：`capacity` = **燃料资源单位数**。质量换算恒定使用 `FUEL_UNIT_MASS = 0.005 t/单位`（即 **1 单位 = 5 kg**），**不存在「1 单位 ≈ 1 kg」的读法**。
- `LF_OX`：`capacity` 为 **LF + OX 合计**单位；单位质量按 KSP 混合比折算，统一取 **0.005 t/单位**的**混合平均质量**。
- **该系数的实证**（由 `03` 撰写者用原版数值反推验证，已核对）：`(wet_mass − dry_mass) / 0.005 = capacity` 在三个原版燃料罐上**精确吻合** —— FL-T800 `(4.5−0.5)/0.005 = 800`、FL-T400 `= 400`、FL-T200 `= 200`，与 KSP 官方容量完全一致。故 R-02 由「猜测的简化」修正为**「与原版数值系统自洽」**。
- `SOLID`：`capacity` 直接等于固体燃料质量换算单位，乘同一系数。

### 4.4 `parts.Engine` — 引擎（需求②）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `part` | OneToOneField(PartCatalog) | CASCADE, related_name='engine' | 对应部件 |
| `series` | CharField(60) | blank, db_index | 引擎系列 |
| `derived_from` | FK(self) | null, blank, on_delete=SET_NULL, related_name='variants' | 改进自 |
| `cycle_type` | CharField(20) | choices=`EngineCycle`, blank | 循环方式 |
| `fuel_type` | CharField(12) | choices=`FuelType` | 推进剂类型 |
| `thrust_asl` | FloatField | default=0 | 海平面推力 (kN) |
| `thrust_vac` | FloatField | default=0 | 真空推力 (kN) |
| `isp_asl` | FloatField | default=0 | 海平面比冲 (s) |
| `isp_vac` | FloatField | default=0 | 真空比冲 (s) |
| `gimbal_range` | FloatField | default=0 | 万向节范围 (°) |
| `min_throttle` | FloatField | default=0 | 最小节流 (%) |
| `is_throttleable` | BooleanField | default=True | 可节流 |
| `has_alternator` | BooleanField | default=False | 带发电机 |
| `alternator_output` | FloatField | default=0 | 发电量 (EC/s) |
| `ignitions` | PositiveIntegerField | default=1 | 点火次数（0=无限） |
| `is_vacuum_optimized` | BooleanField | default=False | 真空优化 |
| `note` | TextField | blank | 备注 |

**`EngineCycle` 枚举**：`GAS_GENERATOR`(燃气发生器) / `STAGED_COMBUSTION`(分级燃烧) / `EXPANDER`(膨胀循环) / `PRESSURE_FED`(挤压式) / `SOLID`(固体) / `JET`(喷气) / `NUCLEAR`(核热) / `MONO`(单元推进剂) / `OTHER`(其他)

**约束**：
- `CheckConstraint(condition=Q(thrust_asl__gte=0) & Q(thrust_vac__gte=0), name='engine_thrust_nonneg')`
- `CheckConstraint(condition=Q(min_throttle__gte=0) & Q(min_throttle__lte=100), name='engine_min_throttle_range')`
- 模型 `clean()`：`thrust_vac >= thrust_asl`（真空推力不应低于海平面）
- **`series` 取代 `EngineFamily`**：`AJ10`、`XLR81`、`LV-909` 这类分组写在此列；`derived_from` 记录变体血缘。

### 4.5 `parts.ScienceInstrument` — 科学设备（需求③）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `part` | OneToOneField(PartCatalog) | CASCADE, related_name='science_instrument' | 对应部件 |
| `experiment_type` | CharField(40) | — | 实验类型 |
| `data_value` | FloatField | default=0 | 基础科学数据量 (Mits) |
| `is_repeatable` | BooleanField | default=False | 可重复使用 |
| `requires_crew` | BooleanField | default=False | 需要乘员 |
| `requires_surface` | BooleanField | default=False | 需要着陆/地表 |
| `transmit_efficiency` | FloatField | default=100 | 传输效率 (%) |
| `has_storage` | BooleanField | default=False | 自带数据存储 |
| `storage_capacity` | FloatField | default=0 | 数据存储容量 (Mits) |
| `note` | TextField | blank | 备注 |

**约束**：模型 `clean()`：`0 <= transmit_efficiency <= 100`。

### 4.6 `carriers.CarrierModel` — 运载火箭型号（改造自 `Carrier`）

| 字段 | 类型 | 约束 | 中文标签 | 旧字段 |
|---|---|---|---|---|
| `id` | BigAutoField | PK | | `Cno` → 由 `code` 承担 |
| `code` | CharField(24) | unique, db_index | 火箭代号 | ← `Cno` |
| `name` | CharField(80) | unique | 火箭名称 | ← `Cname` |
| `series` | CharField(60) | blank, db_index | 系列 | **新增**（替代族） |
| `derived_from` | FK(self) | null, blank, SET_NULL, **related_name='variants'** | 改进自 | **新增** |
| `manufacturer` | CharField(60) | blank | 制造商 | **新增** |
| `diameter` | FloatField | null, blank | 最大直径 (m) | ← `Cd` |
| `height` | FloatField | null, blank | 总高 (m) | **新增** |
| `first_flight_ut` | FloatField | null, blank | 首飞时间 (UT) | ← `Cmaiden`（DATE→UT） |
| `crew_capacity` | PositiveIntegerField | default=0 | 乘员容量 | **新增** |
| `cost` | PositiveIntegerField | default=0 | 造价 (√) | ← `Ccost` |
| `is_reusable` | BooleanField | default=False | 可回收复用 | **新增** |
| `max_payload_mass` | FloatField | null, blank | 设计最大载荷 (t) | ← 由 `Cleo` 语义弱化而来 |
| `description` | TextField | blank | 设计说明 | ← `Cconfig` 语义扩展 |
| `created_at` / `updated_at` | DateTimeField | auto | | **新增** |

**被移除的旧字段**：`Cleo`(LEO 运力)、`Cgto`(GTO 运力)、`Cmass`、`Cthrust`、`Cratio`。**`Cconfig` 不在此列 —— 它是「语义扩展」而非移除**（其内容映射到 `description`，且见 11.4：`Cconfig` 里已含 KSP 部件串，是 路线 B 迁移时的意外收获）。
**移除理由（须写入 `07-重构方案`）**：这些是**从级配置派生**的量。在有了 `Stage` + `StageTank` + `Engine` 之后，LEO 运力/总质量/最大推力/推重比都能算出来（见 `06-核心计算设计`），再手工录入一份就是**冗余数据，必然与级配置漂移**。这是本次重构最实质的数据模型改进之一。

**运力是否保留？** 保留 `max_payload_mass` 作为**玩家声明的设计目标**（设计意图，非计算结果），与计算值在界面上并列显示，不一致时给出提示。

### 4.7 `payloads.PayloadModel` — 有效载荷型号（改造自 `Payload`）

| 字段 | 类型 | 约束 | 中文标签 | 旧字段 |
|---|---|---|---|---|
| `id` | BigAutoField | PK | | `Pno` → 由 `code` 承担 |
| `code` | CharField(24) | unique, db_index | 载荷代号 | ← `Pno` |
| `name` | CharField(80) | unique | 载荷名称 | ← `Pname` |
| `series` | CharField(60) | blank, db_index | 系列 | **新增** |
| `derived_from` | FK(self) | null, blank, **SET_NULL, related_name='variants'** | 改进自 | **新增** |
| `payload_type` | CharField(20) | choices=`PayloadType` | 载荷类型 | ← `Ptype`（枚举化） |
| `mass` | FloatField | default=0 | 载荷质量 (t) | ← `Pmass` |
| `diameter` | FloatField | null, blank | 最小整流罩直径 (m) | ← `Pd` |
| `crew_capacity` | PositiveIntegerField | default=0 | 乘员容量 | **新增** |
| `science_capacity` | FloatField | default=0 | 科学数据容量 (Mits) | **新增** |
| `has_docking_port` | BooleanField | default=False | 带对接端口 | **新增** |
| `cost` | PositiveIntegerField | default=0 | 造价 (√) | **新增** |
| `instruments` | TextField | blank | 搭载仪器说明 | ← `Pconfig` |
| `description` | TextField | blank | 说明 | **新增** |
| `created_at` / `updated_at` | DateTimeField | auto | | **新增** |

**`PayloadType` 枚举**：`CREW_CAPSULE`(载人舱) / `CARGO`(货运舱) / `SATELLITE`(卫星) / `PROBE`(探测器) / `LANDER`(着陆器) / `STATION_MODULE`(空间站模块) / `ROVER`(巡视器) / `OTHER`(其他)

### 4.8 `stages.Stage` — 级（需求⑥，「级间段」）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `owner_type` | CharField(10) | choices=`StageOwnerType` | 所属类型 |
| `carrier` | FK(CarrierModel) | null, blank, CASCADE, related_name='stages' | 所属火箭 |
| `payload` | FK(PayloadModel) | null, blank, CASCADE, related_name='stages' | 所属载荷 |
| `stage_order` | PositiveIntegerField | — | 级序号 |
| `name` | CharField(60) | blank | 级名称 |
| `engine` | FK(Engine) | null, blank, PROTECT, related_name='stages' | 主引擎 |
| `engine_count` | PositiveIntegerField | default=1 | 引擎数量 |
| `is_radial_engine` | BooleanField | default=False | 引擎径向安装 |
| `separation_type` | CharField(16) | choices=`SeparationType`, blank | 分离方式 |
| `decoupler_mass` | FloatField | default=0 | 分离件质量 (t) |
| `has_fairing` | BooleanField | default=False | 此级带整流罩 |
| `min_throttle_used` | FloatField | null, blank | 实际使用的节流上限 (%) |
| `note` | TextField | blank | 备注 |
| `created_at` / `updated_at` | DateTimeField | auto | |

**`StageOwnerType` 枚举**：`CARRIER`(火箭) / `PAYLOAD`(载荷)
**`SeparationType` 枚举**：`STACK_DECOUPLER`(堆叠分离器) / `RADIAL_DECOUPLER`(径向分离器) / `DOCKING`(对接分离) / `NONE`(不分离) / `OTHER`(其他)

**约束（关键）**：
```python
CheckConstraint(
    condition=(
        Q(owner_type='CARRIER', carrier__isnull=False, payload__isnull=True) |
        Q(owner_type='PAYLOAD', payload__isnull=False, carrier__isnull=True)
    ),
    name='stage_exactly_one_owner',
)
UniqueConstraint(fields=['carrier', 'stage_order'], name='uniq_carrier_stage_order')
UniqueConstraint(fields=['payload', 'stage_order'], name='uniq_payload_stage_order')
CheckConstraint(condition=Q(stage_order__gte=1), name='stage_order_positive')
CheckConstraint(condition=Q(engine_count__gte=1), name='stage_engine_count_positive')
```

**设计说明**：
- 用 `owner_type` + 双可空 FK 实现多态（**不用 Django `GenericForeignKey`**，因为 ContentType 多态**无法建立数据库级外键与 CHECK**）。此写法在 SQLite 与 MySQL 上均可移植。
- **`stage_order` 是 `ek` 教的关键：级位置敏感。** `ek.LV(name, family, desc, *stages)` 用参数顺序表达；关系库必须显式落列。
- **★ `stage_order` 方向约定（全项目唯一权威，`03`/`05`/`06` 必须与此一致）**：
  - **`stage_order = 1` 表示「第 1 级」= 发射时最先点火、位于最下方的那一级**（起飞级 / 助推+一级）；向上递增，最大序号为最上一级（接近载荷）。
  - **依据**：与 KSP 游戏内建堆栈分离组（staging stack）的编号一致 —— KSP 中空格键触发的第一个分离事件就是「第 1 级」；也与 `ek.LV(*stages)` 的参数序（助推级在前、上面级在后）一致。
  - **页面渲染方向**：按 `stage_order` **降序自上而下**显示（最上一级在表格顶部、第 1 级在底部），符合火箭的物理外观；界面须常驻一行方向提示。
  - **Δv 计算顺序**：从 `stage_order = 1` 开始逐级向上累加（先算第 1 级的 `m0`，此时「上方所有级质量」= 序号大于 1 的全部级 + 载荷）。
  - **注意与 KSP 一个常见混淆的区别**：KSP 里「第 1 级」指**最先点火**而非「最上面一级」；本约定跟随 KSP。
- 火箭与载荷共用一张 `Stage` 表：两者级以上语义完全一致，避免抄两张平行表（此为相对 `ek` 的改进——`ek` 的 `LV` 与 `Aircraft` 就是两份近乎重复的代码）。

### 4.9 `stages.StageTank` — 级-燃料罐挂载（需求⑥）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `stage` | FK(Stage) | CASCADE, related_name='tanks' | 所属级 |
| `fuel_tank` | FK(FuelTank) | PROTECT, related_name='stage_usages' | 燃料罐 |
| `quantity` | PositiveIntegerField | default=1 | 数量 |
| `mount_position` | CharField(10) | choices=`MountPosition`, default='INLINE' | 安装方式 |
| `note` | CharField(100) | blank | 备注 |

**`MountPosition` 枚举**：`INLINE`(堆叠) / `RADIAL`(径向挂载)

**约束**：
```python
UniqueConstraint(fields=['stage', 'fuel_tank', 'mount_position'], name='uniq_stage_tank_mount')
CheckConstraint(condition=Q(quantity__gte=1), name='stagetank_quantity_positive')
```

**设计说明**：一级挂 n 个燃料罐 —— 同型用 `quantity` 压缩（如 4 个 FL-T800 = 一行 `quantity=4`），异型多行。这与 `ek` 的 `Stage(engine, count)` 思路一致。

### 4.10 `sites.Site` — 发射场（改造自 `Site`）

| 字段 | 类型 | 约束 | 中文标签 | 旧字段 |
|---|---|---|---|---|
| `id` | BigAutoField | PK | | `Sno` → 由 `code` 承担 |
| `code` | CharField(24) | unique, db_index | 发射场代号 | ← `Sno` |
| `name` | CharField(60) | unique | 发射场名称 | ← `Sname` |
| `body` | FK(Body) | PROTECT, related_name='sites' | 所在天体 | **新增** |
| `latitude` | FloatField | null, blank | 纬度 (°) | ← `Slatitude`（CHAR(6)→Float） |
| `longitude` | FloatField | null, blank | 经度 (°) | ← `Slongitude`（CHAR(6)→Float） |
| `altitude` | FloatField | default=0 | 海拔 (m) | **新增** |
| `pad_level` | PositiveIntegerField | default=1 | 发射台等级 | **新增** |
| `max_mass` | FloatField | null, blank | 最大起飞质量 (t) | **新增** |
| `max_diameter` | FloatField | null, blank | 最大直径限制 (m) | **新增** |
| `is_operational` | BooleanField | default=True | 可用 | **新增** |
| `description` | TextField | blank | 说明 | **新增** |
| `created_at` / `updated_at` | DateTimeField | auto | | **新增** |

**旧类型改造理由**：`Slatitude`/`Slongitude` 原为 `CHAR(6)`，且**实际存入的是带方位后缀的字符串**（`arock.sql` 第 49–52 行：`'40.00N'`、`'100.0E'`）。这带来三个实际问题：
1. **无法直接参与计算** —— 球面距离、发射方位角等需要数值，字符串要先解析；
2. **KSP 需要小数精度与负值** —— 南半球/西半球的发射场纬度是负数，`CHAR(6)` 配 `'N'/'E'` 后缀的写法无法自然表达（只能靠后缀）；
3. **无法排序与范围查询** —— 字符串排序会把 `'100.0E'` 排在 `'28.00N'` 前面。

改 `FloatField`（纯十进制度数）后，上述三点一并解决。若需要保留旧数据的方位后缀语义，在 `07` 的 路线 B 迁移脚本中做一次解析（`'40.00N'→40.0`、`'100.0E'→100.0`，并据 S/W 取负）。

**约束**：模型 `clean()`：`-90 <= latitude <= 90`，`-180 <= longitude <= 180`。

### 4.11 `launches.FlightLog` — 发射日志（替代 `SCP`）

| 字段 | 类型 | 约束 | 中文标签 | 旧字段 |
|---|---|---|---|---|
| `id` | BigAutoField | PK | | `SCPno` → 由 `code` 承担 |
| `code` | CharField(24) | unique, db_index | 任务编号 | ← `SCPno`，**保留 `SCP-` 前缀** |
| `name` | CharField(80) | — | 任务名称 | ← `SCPname` |
| `state` | CharField(12) | choices=`FlightState`, default='PLANNED', db_index | 任务状态 | ← `State`（枚举化） |
| `planned_ut` | FloatField | null, blank | 计划发射时间 (UT) | **新增**（核心诉求） |
| `actual_ut` | FloatField | null, blank | 实际发射时间 (UT) | ← `SCPdate`（DATE→UT） |
| `carrier` | FK(CarrierModel) | PROTECT, related_name='flights' | 运载火箭 | ← `Cno` |
| `payload` | FK(PayloadModel) | null, blank, PROTECT, related_name='flights' | 有效载荷 | ← `Pno` |
| `site` | FK(Site) | PROTECT, related_name='flights' | 发射场 | ← `Sno` |
| `crew_count` | PositiveIntegerField | default=0 | 乘员数 | **新增** |
| `result_code` | IntegerField | null, blank | 结果编码 | ← 语义来自 `ek.Launch.result` |
| `rest_dv` | IntegerField | null, blank | 剩余 Δv (m/s) | ← `Restdv` |
| `cost` | PositiveIntegerField | default=0 | 任务成本 (√) | ← `SCPcost` |
| `detail` | TextField | blank | 任务详情 | ← `Detail` |
| `created_at` / `updated_at` | DateTimeField | auto | | **新增** |

**`FlightState` 枚举**：`PLANNED`(计划中) / `COUNTDOWN`(发射准备) / `LAUNCHED`(已发射) / `FAILED`(发射失败) / `CANCELLED`(已取消)

**`result_code` 语义（照搬 `ek.Launch` 的编码，写入 `help_text`）**：
| 值 | 含义 |
|---|---|
| `NULL` | 尚未执行（`state=PLANNED`） |
| `-2` | 台架中止（T-0 前失败，发射夹未释放） |
| `-1` | 任务失败（各级工作正常，但设计缺陷导致任务失败） |
| `0` | 成功 |
| `>0` | 第 n 级失效 |

**约束**：
- `CheckConstraint(condition=Q(result_code__isnull=True) | Q(result_code__gte=-2), name='flight_result_code_range')`
- 模型 `clean()`：`state` 为 `PLANNED` 时 `actual_ut` 应为空；`state` 为 `LAUNCHED/FAILED` 时 `actual_ut` 必填。**此业务规则写在 `clean()` 而非 DB CHECK**，便于给出友好错误提示。
- `Index(fields=['state', 'planned_ut'])`（「发射日程」视图的主查询）

**旧字段 `SCPno CHAR(7)` → `code`**：`ek` 的 `Launch.result` 让我确认了「结果应为有语义的编码而非自由文本」，此处一并采纳。

### 4.12 `programs.Program` — 航天计划（需求⑤，「1」端）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 计划代号 |
| `name` | CharField(80) | unique | 计划名称 |
| `objective` | TextField | — | 计划目标 |
| `status` | CharField(12) | choices=`ProgramStatus`, default='PLANNED', db_index | 计划状态 |
| `target_body` | FK(Body) | null, blank, SET_NULL, related_name='programs' | 主要目标天体 |
| `start_ut` | FloatField | null, blank | 计划开始 (UT) |
| `end_ut` | FloatField | null, blank | 计划结束 (UT) |
| `budget` | PositiveIntegerField | null, blank | 预算 (√) |
| `spent` | PositiveIntegerField | default=0 | 已花费 (√) |
| `priority` | PositiveIntegerField | default=3 | 优先级 (1 最高) |
| `description` | TextField | blank | 说明 |
| `created_at` / `updated_at` | DateTimeField | auto | |

**`ProgramStatus` 枚举**：`PLANNED`(规划中) / `ACTIVE`(进行中) / `COMPLETED`(已完成) / `CANCELLED`(已取消)

**约束**：`CheckConstraint(condition=Q(priority__gte=1) & Q(priority__lte=5), name='program_priority_range')`；模型 `clean()`：`end_ut >= start_ut`（两者都非空时）。

### 4.13 `programs.ProgramLink` — 计划成员链接（需求⑤，「n」端）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `program` | FK(Program) | CASCADE, related_name='links' | 所属计划 |
| `object_type` | CharField(12) | choices=`ProgramObjectType` | 成员类型 |
| `carrier` | FK(CarrierModel) | null, blank, CASCADE, related_name='program_links' | 火箭 |
| `payload` | FK(PayloadModel) | null, blank, CASCADE, related_name='program_links' | 载荷 |
| `flight` | FK(FlightLog) | null, blank, CASCADE, related_name='program_links' | 发射日志 |
| `site` | FK(Site) | null, blank, CASCADE, related_name='program_links' | 发射场 |
| `spacecraft` | FK(Spacecraft) | null, blank, CASCADE, related_name='program_links' | 在轨航天器 |
| `role_note` | CharField(120) | blank | 在本计划中的角色 |
| `added_at` | DateTimeField | auto_now_add | 加入时间 |

**`ProgramObjectType` 枚举**：`CARRIER`(火箭) / `PAYLOAD`(载荷) / `FLIGHT`(发射日志) / `SITE`(发射场) / `SPACECRAFT`(航天器)

**约束（关键，决策 D-06）**：
```python
CheckConstraint(
    condition=(
        Q(object_type='CARRIER',    carrier__isnull=False, payload__isnull=True,  flight__isnull=True, site__isnull=True, spacecraft__isnull=True) |
        Q(object_type='PAYLOAD',    carrier__isnull=True,  payload__isnull=False, flight__isnull=True, site__isnull=True, spacecraft__isnull=True) |
        Q(object_type='FLIGHT',     carrier__isnull=True,  payload__isnull=True,  flight__isnull=False, site__isnull=True, spacecraft__isnull=True) |
        Q(object_type='SITE',       carrier__isnull=True,  payload__isnull=True,  flight__isnull=True, site__isnull=False, spacecraft__isnull=True) |
        Q(object_type='SPACECRAFT', carrier__isnull=True,  payload__isnull=True,  flight__isnull=True, site__isnull=True, spacecraft__isnull=False)
    ),
    name='programlink_exactly_one_object',
)
UniqueConstraint(fields=['program', 'object_type', 'carrier'], name='uniq_program_carrier')
# 同理为 payload/flight/site/spacecraft 各建一个（SQLite 中 NULL 不参与唯一性，故 5 条唯一约束互不干扰）
```

**基数的准确表述**：
- `Program (1) ── (n) ProgramLink`：一个计划可挂任意多个成员。
- **一个成员对象最多归属一个计划**（由 5 条 `UniqueConstraint` 保证）。这是「1 计划 : n 对象」最贴合你原话的实现——「1 航天计划」对「n 其他对象」。
- 若将来需要「一个对象参与多个计划」，只需移除那 5 条唯一约束，**表结构无需改动**。这一点写入 `03` 的扩展说明。

### 4.14 `spacecraft.Spacecraft` — 在轨航天器（需求④）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 航天器代号 |
| `name` | CharField(80) | unique | 航天器名称 |
| `source_flight` | FK(FlightLog) | null, blank, SET_NULL, related_name='spacecraft' | 来源发射 |
| `source_carrier` | FK(CarrierModel) | null, blank, SET_NULL, related_name='spacecraft' | 来源火箭 |
| `source_payload` | FK(PayloadModel) | null, blank, SET_NULL, related_name='spacecraft' | 载荷 |
| `body` | FK(Body) | PROTECT, related_name='spacecraft' | 当前所在天体 |
| `situation` | CharField(12) | choices=`Situation`, db_index | 当前状态 |
| `is_active` | BooleanField | default=True, db_index | 在役 |
| `is_controlled` | BooleanField | default=True | 可操控 |
| `crew_count` | PositiveIntegerField | default=0 | 乘员数 |
| `sma` | FloatField | null, blank | 半长轴 (m) |
| `eccentricity` | FloatField | null, blank | 离心率 |
| `inclination` | FloatField | null, blank | 轨道倾角 (°) |
| `lan` | FloatField | null, blank | 升交点经度 (°) |
| `arg_pe` | FloatField | null, blank | 近拱点幅角 (°) |
| `true_anomaly` | FloatField | null, blank | 真近点角 (°) |
| `mean_anomaly_at_epoch` | FloatField | null, blank | 历元平近点角 (°) |
| `epoch_ut` | FloatField | null, blank | 轨道历元 (UT) |
| `cached_period_sec` | FloatField | null, blank | 周期快照 (s) |
| `altitude` | FloatField | null, blank | 当前高度 (m) |
| `note` | TextField | blank | 备注 |
| `created_at` / `updated_at` | DateTimeField | auto | |

**`Situation` 枚举**（对应 KSP 飞行状态）：`LANDED`(已着陆) / `SPLASHED`(水面溅落) / `FLYING`(大气内飞行) / `ORBITING`(环绕轨道) / `ESCAPING`(逃逸中) / `DOCKED`(已对接) / `DESTROYED`(已损毁)

**约束**：
- **约束（`eccentricity` 的争议在此定死）**：
  - **DB 级 CHECK**：仅 `eccentricity >= 0`（不强制 `< 1`）。理由：**`situation=ESCAPING` 的逃逸轨道天然是 `e ≥ 1` 的双曲线**，若强制 `e < 1` 则无法录入真实存在的逃逸任务——这是「物理正确」优先于「便于校验」的取舍。
  - **模型 `clean()`**：当 `situation` 为环绕类（`ORBITING`/`DOCKED`）且 `eccentricity` 非空时，校验 `0 <= e < 1` 并给出中文提示；`ESCAPING` 时允许 `e >= 1`。
  - **周期计算的条件**：`e >= 1` 时 $T$ 无意义（非闭合轨道），`services.orbital.orbital_period()` 返回 `None`，界面显示「双曲线轨迹，无周期」而非报错。
  - `0 <= inclination <= 180`（`clean()`）
- 模型 `clean()` 另有：`sma` 非空时须 `> Body.radius`（跨表校验，见 4.0 说明为何不放 DB CHECK）
- `Index(fields=['body', 'is_active', 'situation'])`

**不落库的派生量**：`periapsis`、`apoapsis`、`period`、`orbital_speed` 一律**实时计算**，不建列（避免与 `sma`/`eccentricity` 漂移）。

**`cached_period_sec` 的双重角色**：`sma` 为唯一权威输入，`period` 默认由 $T = 2\pi\sqrt{a^3/\mu}$ 计算。`cached_period_sec` 是**玩家从 MechJeb/KER 抄录的周期快照**，仅作对照展示；界面上并列显示「计算值 / 录入值」，偏差超阈值时给出提示。这与 `CarrierModel.max_payload_mass`（声明值 vs 计算值）是同一套设计模式。

### 4.15 主键与 `code` 规范

| 项 | 规范 |
|---|---|
| 主键 | `id`，`BigAutoField`（Django 默认，`DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`） |
| `code` | 每张业务表都有（`Body`/`PartCatalog`/`CarrierModel`/`PayloadModel`/`Site`/`FlightLog`/`Program`/`Spacecraft`）；`Engine`/`FuelTank`/`ScienceInstrument` 通过其 `part.code` 定位，另设 `code` |
| 格式 | `前缀-主体[-序号]`，全大写 ASCII，**总长 ≤ 24** |
| 前缀表 | `BODY-` 天体 ｜ `PART-` 部件 ｜ `TANK-` 燃料罐 ｜ `ENG-` 引擎 ｜ `SCI-` 科学设备 ｜ `LV-` 火箭 ｜ `PL-` 载荷 ｜ `PAD-` 发射场 ｜ `SCP-` 发射日志 ｜ `PRG-` 计划 ｜ `S/C-` 航天器 |
| 示例 | `LV-DAVY2B`、`ENG-AJ10-37`、`PAD-KSC-LC1`、**`SCP-2026-014`**、`PRG-DUNA-01`、`S/C-KERBIN-SAT1` |
| 校验 | 正则 `^[A-Z0-9][A-Z0-9/\-]{1,22}[A-Z0-9]$`；`clean()` 中强制 |
| **`SCP-` 前缀保留** | 旧表 `SCP` 的名字不再作为表名，但**任务编号前缀 `SCP-` 保留**，使旧数据与界面习惯延续（决策记录 D-11 相关） |

### 4.16 删除策略（`on_delete` 总表）

| 父 → 子 | 策略 | 理由 |
|---|---|---|
| `CarrierModel` → `Stage` | `CASCADE` | 级是火箭的组成部分，火箭没了级无意义 |
| `PayloadModel` → `Stage` | `CASCADE` | 同上 |
| `Stage` → `StageTank` | `CASCADE` | 挂载记录随级消失 |
| `PartCatalog` → `FuelTank`/`Engine`/`ScienceInstrument` | `CASCADE` | 1:1 子表随超类消失 |
| `Engine` → `Stage.engine` | **`PROTECT`** | 引擎被级引用时禁止删除，防脏数据（沿用旧项目「删除前检查外键关联」的意图，但改由数据库强制） |
| `FuelTank` → `StageTank` | **`PROTECT`** | 同上 |
| `Body` → `Site` / `Spacecraft` | **`PROTECT`** | 有发射场或航天器的天体不可删 |
| `CarrierModel`/`PayloadModel`/`Site` → `FlightLog` | **`PROTECT`** | 发射历史不可因删火箭而丢失 |
| `FlightLog` → `Spacecraft.source_flight` | `SET_NULL` | 航天器在轨，日志删除不应连带删除在轨资产 |
| `CarrierModel`/`PayloadModel` → `Spacecraft.source_*` | `SET_NULL` | 同上 |
| `Program` → `ProgramLink` | `CASCADE` | 计划删除则成员关系消失（成员对象本身保留） |
| 任意对象 → `ProgramLink.*` | `CASCADE` | 对象删除则其计划关系消失 |
| `Body.parent` | `PROTECT` | 有子天体的天体不可删 |
| `Body` → `Program.target_body` | `SET_NULL` | 计划的「主要目标天体」是描述性字段，天体定义调整不应连带删除计划 |
| `*.derived_from` | `SET_NULL` | 变体来源删除不应连带删除变体 |

---

## 5. 应用结构与分层

### 5.1 目标目录结构

```
rocket_manage/
├── manage.py
├── requirements.txt
├── db.sqlite3                      # 运行后生成（.gitignore）
├── config/                         # 项目配置（原「工程」）
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py                 # 公共配置
│   │   ├── dev.py                  # DEBUG=True, SQLite
│   │   └── prod.py                 # 备用
│   ├── urls.py                     # 根路由（include 各 app）
│   ├── wsgi.py
│   └── asgi.py
├── core/                           # 天体 + 首页 + 公共基类
│   ├── models.py                   # Body
│   ├── views.py                    # HomeView, BodyListView/Detail
│   ├── admin.py                    # BodyAdmin（树形缩进显示）
│   ├── forms.py
│   ├── constants.py                # ★ KSP 物理常数集中定义（第 9 节）
│   ├── mixins.py                   # CodeModel / TimeStampedModel（统一命名：CodeModel，非 CodeModelMixin）
│   └── urls.py
├── parts/                          # PartCatalog FuelTank Engine ScienceInstrument
├── carriers/                       # CarrierModel
├── payloads/                       # PayloadModel
├── stages/                         # Stage StageTank + StageFormSet 服务
├── sites/                          # Site
├── launches/                       # FlightLog + 发射日程视图
├── programs/                       # Program ProgramLink
├── spacecraft/                     # Spacecraft + 轨道展示
├── services/                       # ★ 领域计算（无 Django 视图依赖，可单测）
│   ├── orbital.py                  # 周期 / 近远拱点 / 速度
│   ├── deltav.py                   # 齐奥尔科夫斯基 / 推重比 / 各级累加
│   └── stats.py                    # 计划进度 / 统计聚合
├── templates/
│   ├── base.html                   # 新布局（替代旧 layout.html）
│   ├── includes/                   # _navbar _footer _messages _formhelpers
│   ├── core/ carriers/ payloads/ stages/ sites/ launches/ programs/ spacecraft/ parts/
├── static/
│   ├── css/style.css
│   └── js/stage_formset.js         # ★ 级表单动态增删行
└── docs/                           # 本文档集
```

**与旧结构的关键差异**：旧项目 `manage.py` 是**唯一入口且含全部路由**（992 行巨石，实测 22 个 `@app.route`；「26」这个数字是 22 个路由 + `is_logged_in` + `check_foreign_key` + 内层 `wrap` + `__main__` 块的顶层定义计数，**不是路由数**）。新结构按 app 拆分，**`manage.py` 只保留 Django 标准入口**。

### 5.2 分层职责

| 层 | 位置 | 职责 | 禁止 |
|---|---|---|---|
| 模型层 | `<app>/models.py` | 表结构、字段约束、`clean()` 业务校验、简单属性 | 不写 HTTP 相关逻辑 |
| 服务层 | `services/*.py` | 物理计算、统计聚合、跨模型业务事务 | **不 import Django 视图或 request** |
| 表单层 | `<app>/forms.py` | 输入校验、`ModelForm`、FormSet | 不直接操作数据库 |
| 视图层 | `<app>/views.py` | 编排（取数 → 调服务 → 渲染） | **不写业务规则**（旧项目把 SQL 与规则混在视图里，是主要债务） |
| 管理后台 | `<app>/admin.py` | Django Admin 配置（`list_display`/`list_filter`/内联） | — |
| 路由层 | `<app>/urls.py` | URL → 视图映射 | — |

**`services/` 独立于 app 的意义**：物理计算与统计可被 Admin、视图、管理命令、单元测试**共同复用**，且不依赖 Django 请求上下文 —— 这让 `06-核心计算设计` 的测试变得可能。这是旧项目完全缺失的层次。

### 5.3 Django Admin 配置要点（省掉 70% CRUD 的地方）

| 模型 | Admin 要点 |
|---|---|
| `Body` | `list_display` 缩进名（用 `depth` 前缀）、`list_filter=[is_star, has_atmosphere]`、`search_fields` |
| `PartCatalog` | `list_display=[code, name, part_type, diameter, dry_mass, cost]`、`list_filter=[part_type, manufacturer]`、`list_editable=[cost]` |
| `Engine` | `list_display` 含推力/比冲；`list_filter=[cycle_type, fuel_type, series]` |
| `CarrierModel` | **`StageInline` 内联编辑其级**（`extra=0`，因级数量不定）；`list_filter=[series, is_reusable]` |
| `PayloadModel` | 同上内联 |
| `Stage` | `list_display=[owner, stage_order, engine, engine_count]`；`StageTankInline` 内联（`extra=1`） |
| `FlightLog` | `list_display=[code, name, state, planned_ut, actual_ut, carrier]`；`list_filter=[state, site]`；`date_hierarchy` 不适用（UT 为浮点），改用自定义 `planned_ut` 分组筛选 |
| `Program` | **`ProgramLinkInline`（多态，需自定义表单）**；`list_filter=[status, priority]` |
| `Spacecraft` | `list_display` 含计算出的周期与近远拱点（`readonly_fields` 调 `services.orbital`） |

**⚠️ 多态内联的已知限制（必须写入 `04`/`05`）**：Django 的 `GenericTabularInline` 依赖 `ContentType`，**会绕过我们设计的「恰好一个非空」CHECK 约束**。故 `Stage` 与 `ProgramLink` 的 Admin **不使用 Generic 内联**，改为：
- `Stage`：在 `CarrierModelAdmin` / `PayloadModelAdmin` 中定义**两个独立的普通 `TabularInline`**（一个 `fk_name='carrier'`，一个 `fk_name='payload'`），各自只显示对应类型；`owner_type` 在 `save_model`/`save_formset` 中自动填充。
- `ProgramLink`：改用 `ProgramLinkAdmin` 独立维护页（带 `object_type` 过滤），不在 `ProgramAdmin` 内联，避免多态表单复杂度。

---

## 6. URL 路由表

**根路由**：`config/urls.py`

| 前缀 | include |
|---|---|
| `admin/` | `admin.site.urls` |
| `accounts/` | `django.contrib.auth.urls`（登录/登出，复用 Django 内置） |
| `''` | `core.urls`（首页） |
| `parts/` | `parts.urls` |
| `carriers/` | `carriers.urls` |
| `payloads/` | `payloads.urls` |
| `sites/` | `sites.urls` |
| `stages/` | `stages.urls` |
| `launches/` | `launches.urls` |
| `programs/` | `programs.urls` |
| `spacecraft/` | `spacecraft.urls` |

### 6.1 各 app 路由明细（全部采用 Django 通用视图命名约定）

| 名称 | URL | 视图 | 方法 | 登录 | 说明 |
|---|---|---|---|---|---|
| `home` | `/` | `core.views.HomeView` | GET | 否 | 首页看板：近期发射 + 计划概览 |
| `body_list` | `/bodies/` | `core.views.BodyListView` | GET | 否 | 天体树浏览 |
| `body_detail` | `/bodies/<int:pk>/` | `core.views.BodyDetailView` | GET | 否 | 天体详情（含其发射场/航天器） |
| `part_list` | `/parts/` | `parts.views.PartListView` | GET | 否 | 部件库（按 `part_type` 筛选） |
| `part_detail` | `/parts/<int:pk>/` | `parts.views.PartDetailView` | GET | 否 | 部件详情 |
| `part_create` | `/parts/add/` | `parts.views.PartCreateView` | GET/POST | **是** | 新增部件 |
| `part_update` | `/parts/<int:pk>/edit/` | `parts.views.PartUpdateView` | GET/POST | **是** | 编辑 |
| `part_delete` | `/parts/<int:pk>/delete/` | `parts.views.PartDeleteView` | GET/POST | **是** | 删除确认 |
| `carrier_list` | `/carriers/` | `carriers.views.CarrierListView` | GET | 否 | 火箭列表（按系列/是否复用筛选） |
| `carrier_detail` | `/carriers/<int:pk>/` | `carriers.views.CarrierDetailView` | GET | 否 | 详情：**级序列表 + Δv/推重比汇总** |
| `carrier_create` | `/carriers/add/` | `carriers.views.CarrierCreateView` | GET/POST | **是** | **含级 FormSet** |
| `carrier_update` | `/carriers/<int:pk>/edit/` | `carriers.views.CarrierUpdateView` | GET/POST | **是** | 含级 FormSet |
| `carrier_delete` | `/carriers/<int:pk>/delete/` | `carriers.views.CarrierDeleteView` | GET/POST | **是** | 删除确认（提示级将连带删除） |
| `carrier_variants` | `/carriers/<int:pk>/variants/` | `carriers.views.CarrierVariantTreeView` | GET | 否 | 变体血缘树（`derived_from` 递归） |
| `payload_list` | `/payloads/` | `payloads.views.PayloadListView` | GET | 否 | — |
| `payload_detail` | `/payloads/<int:pk>/` | `payloads.views.PayloadDetailView` | GET | 否 | 详情：级序列 + 质量 |
| `payload_create` | `/payloads/add/` | `payloads.views.PayloadCreateView` | GET/POST | **是** | **含级 FormSet** |
| `payload_update` | `/payloads/<int:pk>/edit/` | `payloads.views.PayloadUpdateView` | GET/POST | **是** | 含级 FormSet |
| `payload_delete` | `/payloads/<int:pk>/delete/` | `payloads.views.PayloadDeleteView` | GET/POST | **是** | — |
| `stage_create` | `/stages/add/?owner_type=&owner_id=` | `stages.views.StageCreateView` | GET/POST | **是** | 独立新增一级（供非 FormSet 路径使用） |
| `stage_update` | `/stages/<int:pk>/edit/` | `stages.views.StageUpdateView` | GET/POST | **是** | 含 `StageTank` FormSet |
| `stage_delete` | `/stages/<int:pk>/delete/` | `stages.views.StageDeleteView` | GET/POST | **是** | — |
| `stage_reorder` | `/stages/reorder/` | `stages.views.StageReorderView` | POST | **是** | 批量调整 `stage_order`（AJAX JSON） |
| `site_list` | `/sites/` | `sites.views.SiteListView` | GET | 否 | — |
| `site_detail` | `/sites/<int:pk>/` | `sites.views.SiteDetailView` | GET | 否 | — |
| `site_create` | `/sites/add/` | `sites.views.SiteCreateView` | GET/POST | **是** | — |
| `site_update` | `/sites/<int:pk>/edit/` | `sites.views.SiteUpdateView` | GET/POST | **是** | — |
| `site_delete` | `/sites/<int:pk>/delete/` | `sites.views.SiteDeleteView` | GET/POST | **是** | — |
| `flight_list` | `/flights/` | `launches.views.FlightListView` | GET | 否 | 支持按 `state`/`carrier`/`payload`/`site` 筛选 |
| `flight_schedule` | `/flights/schedule/` | `launches.views.FlightScheduleView` | GET | 否 | **★ 发射日程（核心诉求）**：尚未执行的任务按 `planned_ut` 排序 |
| `flight_detail` | `/flights/<int:pk>/` | `launches.views.FlightDetailView` | GET | 否 | — |
| `flight_create` | `/flights/add/` | `launches.views.FlightCreateView` | GET/POST | **是** | 可用于**新建计划** |
| `flight_update` | `/flights/<int:pk>/edit/` | `launches.views.FlightUpdateView` | GET/POST | **是** | — |
| `flight_delete` | `/flights/<int:pk>/delete/` | `launches.views.FlightDeleteView` | GET/POST | **是** | — |
| `flight_launch` | `/flights/<int:pk>/launch/` | `launches.views.FlightLaunchView` | POST | **是** | **一键「执行发射」**：`PLANNED`→`LAUNCHED` 并填 `actual_ut` |
| `program_list` | `/programs/` | `programs.views.ProgramListView` | GET | 否 | — |
| `program_detail` | `/programs/<int:pk>/` | `programs.views.ProgramDetailView` | GET | 否 | **★ 计划总览**：所有成员对象 + 进度 + 预算执行 |
| `program_create` | `/programs/add/` | `programs.views.ProgramCreateView` | GET/POST | **是** | — |
| `program_update` | `/programs/<int:pk>/edit/` | `programs.views.ProgramUpdateView` | GET/POST | **是** | — |
| `program_delete` | `/programs/<int:pk>/delete/` | `programs.views.ProgramDeleteView` | GET/POST | **是** | — |
| `programlink_create` | `/programs/<int:program_pk>/link/add/` | `programs.views.ProgramLinkCreateView` | GET/POST | **是** | 向计划添加成员（按 `object_type` 动态选对象） |
| `programlink_delete` | `/programs/links/<int:pk>/delete/` | `programs.views.ProgramLinkDeleteView` | POST | **是** | 移除成员关系 |
| `spacecraft_list` | `/spacecraft/` | `spacecraft.views.SpacecraftListView` | GET | 否 | **在役航天器**（`is_active=True` 默认） |
| `spacecraft_detail` | `/spacecraft/<int:pk>/` | `spacecraft.views.SpacecraftDetailView` | GET | 否 | 轨道要素 + 计算出的周期/近远拱点 |
| `spacecraft_create` | `/spacecraft/add/` | `spacecraft.views.SpacecraftCreateView` | GET/POST | **是** | — |
| `spacecraft_update` | `/spacecraft/<int:pk>/edit/` | `spacecraft.views.SpacecraftUpdateView` | GET/POST | **是** | — |
| `spacecraft_delete` | `/spacecraft/<int:pk>/delete/` | `spacecraft.views.SpacecraftDeleteView` | GET/POST | **是** | — |
| `spacecraft_orbit_calc` | `/spacecraft/orbit-calc/` | `spacecraft.views.OrbitCalcView` | POST | **是** | **AJAX**：传 `body_id`+`sma`+`eccentricity`，返回周期/近远拱点 |

**登录控制**：列表/详情类视图**公开**（沿用旧项目「浏览无需登录」的设定）；增删改**一律 `LoginRequiredMixin`**（旧项目用 `@is_logged_in` 装饰器实现同一意图）。`DELETE` 类操作**必须是 POST**（旧项目用 GET 触发删除，配合无 CSRF 保护可被跨站触发；Django 的 CSRF 中间件默认开启，且 `DeleteView` 只接受 POST，此项自动修复）。

---

## 7. 页面清单（`05-页面交互设计` 的依据）

| # | 页面 | 模板 | 关键交互 |
|---|---|---|---|
| 1 | 首页看板 | `core/home.html` | 近期发射（5 条）、进行中计划卡片、在役航天器计数 |
| 2 | 天体浏览 | `core/body_list.html` | 树形缩进列表、点击展开 |
| 3 | 部件库 | `parts/part_list.html` | `part_type` 标签页切换、直径/类型筛选、造价排序 |
| 4 | 部件详情 | `parts/part_detail.html` | 按类型显示专有字段（燃料罐/引擎/科学设备三套子块） |
| 5 | 火箭列表 | `carriers/carrier_list.html` | 系列分组、变体标记 |
| 6 | **火箭详情** | `carriers/carrier_detail.html` | **★ 级序列表**（自上而下）、Δv 逐级累加条、推重比、变体血缘树 |
| 7 | **火箭编辑** | `carriers/carrier_form.html` | **★ 级 FormSet 动态增删行**（见下） |
| 8 | 载荷列表/详情/编辑 | `payloads/*` | 同火箭，字段不同 |
| 9 | 发射场列表/编辑 | `sites/*` | 天体选择、经纬度 |
| 10 | 发射日志列表 | `launches/flight_list.html` | 多维筛选（状态/火箭/载荷/发射场）、分页 |
| 11 | **发射日程** | `launches/flight_schedule.html` | **★ 核心诉求页**：按 `planned_ut` 分组的待发任务时间轴；一键「执行发射」 |
| 12 | 发射详情/编辑 | `launches/*` | `planned_ut` 与 `actual_ut` 并列、`result_code` 语义选择器 |
| 13 | 计划列表 | `programs/program_list.html` | 状态/优先级筛选、进度条 |
| 14 | **计划总览** | `programs/program_detail.html` | **★ 1:n 聚合页**：按 `object_type` 分组展示所有成员；预算执行；发射完成率 |
| 15 | 计划成员添加 | `programs/programlink_form.html` | **动态表单**：先选 `object_type`，再 AJAX 加载对应对象下拉 |
| 16 | **在役航天器** | `spacecraft/spacecraft_list.html` | 按天体/状态筛选、周期与近远拱点列 |
| 17 | 航天器详情/编辑 | `spacecraft/*` | **轨道要素表单 + 实时周期计算**（AJAX 调 `orbit_calc`） |

### 7.1 级 FormSet 的动态增删（本项目交互难点）

`carriers/carrier_form.html` 与 `payloads/payload_form.html` 共用同一套逻辑，实现要点：
1. 服务端：Django `inlineformset_factory(CarrierModel, Stage, formset=BaseStageFormSet, extra=2, can_delete=True)`，`BaseStageFormSet.clean()` 校验 `stage_order` 唯一且连续（1..n 无空洞）。
2. 客户端：`static/js/stage_formset.js` 克隆 `empty_form` 模板行实现「+ 添加一级」；「移除」勾选 `DELETE` 隐藏域（Django FormSet 标准做法）。
3. **顺序即 `stage_order`**：拖拽排序（原生 HTML5 `draggable`）后提交时按 DOM 顺序重写隐藏的 `stage_order` 输入，再调 `stage_reorder`。
4. 无构建链：不用 React/Vue，纯 JS + HTML `<template>`。
5. 每一级的燃料罐：在级行内嵌套一层 `StageTank` FormSet（两级 FormSet 嵌套）。**若实现复杂度超预期，降级方案**：级的编辑页（`stage_update`）单独管理燃料罐，火箭表单只管到「级 + 引擎 + 引擎数量」。此降级写入 `08-任务清单` 的可选项。

---

## 8. 核心计算定义（`06-核心计算设计` 的依据）

### 8.1 Δv（齐奥尔科夫斯基公式）
单级：
$$\Delta v = I_{sp} \cdot g_0 \cdot \ln\frac{m_0}{m_f}$$
其中：
- $g_0 = 9.80665\ \text{m/s}^2$（**常数，与所在天体无关** —— 常见错误是用当地重力，必须避免）
- $I_{sp}$：**真空段取 `isp_vac`，大气段取 `isp_asl`**；v1 采用简化：按级所处阶段选择，用户可在表单中显式指定用哪个比冲（默认：第一级用 `isp_asl`，其余用 `isp_vac`）
- $m_0$ = 本级初始质量 = 本级干重 + 本级燃料质量 + 上方所有级质量 + 载荷质量
- $m_f$ = 本级燃尽质量 = $m_0$ − 本级燃料质量

**各级质量构成**：
```
本级干重 = Σ(StageTank 部件干重 × quantity) + Engine.dry_mass × engine_count + decoupler_mass
本级燃料质量 = Σ(FuelTank.capacity × quantity) × FUEL_UNIT_MASS
```
**`FUEL_UNIT_MASS = 0.005 t/单位`**（见 4.3 容量语义；即 1 单位 = 5 kg 混合平均质量）

### 8.2 推重比（TWR）
$$\text{TWR} = \frac{F}{m_0 \cdot g_{\text{local}}}, \qquad g_{\text{local}} = \frac{\mu}{r^2}$$
- $F$ = `Engine.thrust_asl`（起飞判定）或 `thrust_vac`（真空判定）× `engine_count`
- $g_{\text{local}}$ 由 `Body.mu` 与 $r = \text{Body.radius} + \text{altitude}$ 计算；v1 在发射场判定时取 $r = \text{Body.radius}$
- **判定阈值**：起飞级 $\text{TWR} \ge 1.2$ 视为可用，$1.2 \le \text{TWR} \le 1.7$ 提示为合理区间，$> 2.5$ 提示「过推，气动损失大」

### 8.3 轨道周期（★ 需求「周期信息」的落点）
$$T = 2\pi\sqrt{\frac{a^3}{\mu}}$$
- $a$ = `Spacecraft.sma`（半长轴），$\mu$ = `Body.mu`
- **派生量，不落库**（决策 D-12）。理由：$T$ 是 $a$ 与 $\mu$ 的函数，独立存储必然漂移。
- `cached_period_sec` 为玩家从 MechJeb/KER 抄录的快照，仅作对照；偏差 $>1\%$ 时界面提示。
- **KSP 周期单位换算**：KSP 玩家常用「天」表示周期（1 天 = 21600 s）。展示层同时给出秒与天。

### 8.4 近拱点 / 远拱点 / 轨道速度
$$r_p = a(1-e), \qquad r_a = a(1+e)$$
$$v = \sqrt{\mu\left(\frac{2}{r} - \frac{1}{a}\right)} \quad\text{(vis-viva)}$$
`altitude`（相对天体表面高度）= $r - \text{Body.radius}$。

### 8.5 同步轨道高度（派生便利值）
$$a_{\text{sync}} = \left(\mu \left(\frac{T_{\text{sidereal}}}{2\pi}\right)^2\right)^{1/3}$$
Kerbin：$\mu = 3.5316\times10^{12}$、`sidereal_day = 21549.4 s`
→ $a_{\text{sync}} = 3\,463\,331\ \text{m}$，即**高度 ≈ 2 863.33 km**。

> **⚠️ 本节数值已用代码验算**（`T(a_sync, mu)` 回代得 21 549.4 s，偏差 0.0000%）。注意 KSP 社区常引用的「2 868.75 km」对应的是**太阳日 21 600 s** 而非恒星日 21 549.4 s —— `Body` 表同时保留 `sidereal_day` 与 `solar_day` 两列，正是为了消除这种混淆。`06` 文档须明确：**周期公式用恒星日**。

### 8.6 霍曼转移 Δv（v1 只做计算展示，不做规划器）
$$\Delta v_1 = \sqrt{\frac{\mu}{r_1}}\left(\sqrt{\frac{2r_2}{r_1+r_2}} - 1\right), \qquad \Delta v_2 = \sqrt{\frac{\mu}{r_2}}\left(1 - \sqrt{\frac{2r_1}{r_1+r_2}}\right)$$

### 8.7 计算模块 API 约定（`services/`）

```python
# services/orbital.py
def orbital_period(sma: float, mu: float) -> float: ...          # 秒
def apsis(sma: float, eccentricity: float) -> tuple[float, float]:  # (rp, ra) 米
def orbital_velocity(r: float, sma: float, mu: float) -> float:  # m/s
def synchronous_sma(sidereal_day: float, mu: float) -> float:    # 米
def altitude_from_radius(r: float, body_radius: float) -> float: # 米

# services/deltav.py
def stage_dry_mass(stage) -> float: ...
def stage_fuel_mass(stage) -> float: ...
def stage_delta_v(stage, upper_mass: float, use_vacuum_isp: bool) -> float: ...
def vehicle_delta_v(carrier, payload=None) -> list[StageDeltaV]: ...  # 逐级
def liftoff_twr(carrier, payload, body) -> float: ...

# services/stats.py
def program_progress(program) -> ProgramProgress: ...  # 各状态计数、预算执行率
def launch_success_rate(queryset) -> float: ...
def body_activity(body) -> dict: ...   # 该天体下发射场/航天器统计
```

**测试要求**（写入 `08`）：`services/` 三个模块必须有单元测试，用 `manage.py test`；至少覆盖
- 已知 Kerbin 同步轨道周期 ≈ 21600 s（用 `sidereal_day` 反算验算）
- Mun 轨道周期计算与 KSP Wiki 参考值比对
- 单级 Δv 手算样例（给定质量与比冲）
- `services` 在 `mu` 为空/`sma` 为空时返回 `None` 而非抛异常

---

## 9. KSP 物理常数表（`core/constants.py` 的内容）

> 单位一律 SI（米/秒/千克换算的吨）。

```python
G0 = 9.80665              # 标准重力加速度 (m/s²)，Δv 公式用，与天体无关
FUEL_UNIT_MASS = 0.005    # 每单位燃料质量 (t/单位)，见 4.3 容量语义
KERBIN_DAY = 21600.0      # KSP 太阳日 (s)，显示层「天」换算用
```

### 9.1 天体数据（`Body` 的种子数据，`fixtures/bodies.json`）

| 天体 | `code` | `parent` | `radius` (m) | `mu` (m³/s²) | `soi_radius` (m) | `atmosphere_height` (m) | `sidereal_day` (s) | `surface_gravity` (m/s²) | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| Kerbol | `BODY-KERBOL` | — | 261 600 000 | 1.172 332 0×10¹⁸ | ∞（无 SOI 意义） | 0 | 432 000 | 17.13 | `is_star=True` |
| Kerbin | `BODY-KERBIN` | Kerbol | 600 000 | 3.531 600×10¹² | 84 159 286 | 70 000 | 21 549.4 | 9.81 | 母星 |
| Mun | `BODY-MUN` | Kerbin | 200 000 | 6.513 839×10¹⁰ | 2 429 559 | 0 | 138 984 | 1.63 | 潮汐锁定 |
| Minmus | `BODY-MINMUS` | Kerbin | 60 000 | 1.765 800×10⁹ | 2 247 428 | 0 | 40 400 | 0.491 | |
| Duna | `BODY-DUNA` | Kerbol | 320 000 | 3.013 632×10¹¹ | 47 921 949 | 50 000 | 65 517.86 | 2.94 | |
| Ike | `BODY-IKE` | Duna | 130 000 | 1.856 836×10¹⁰ | 1 049 599 | 0 | 65 517.86 | 1.10 | 潮汐锁定 |
| Eve | `BODY-EVE` | Kerbol | 700 000 | 8.171 730×10¹² | 85 109 365 | 90 000 | 80 500 | 16.7 | 厚大气 |
| Gilly | `BODY-GILLY` | Eve | 13 000 | 8.289 455×10⁶ | 126 123 | 0 | 28 255 | 0.049 | |
| Moho | `BODY-MOHO` | Kerbol | 250 000 | 1.686 093×10¹¹ | 9 640 781 | 0 | 1 210 000 | 2.70 | |
| Dres | `BODY-DRES` | Kerbol | 138 000 | 2.148 448×10¹⁰ | 32 832 840 | 0 | 34 800 | 1.13 | |
| Jool | `BODY-JOOL` | Kerbol | 6 000 000 | 2.825 280×10¹⁴ | 2 455 985 042 | 200 000 | 36 000 | 7.85 | 气态巨行星 |
| Laythe | `BODY-LAYTHE` | Jool | 500 000 | 1.962 000×10¹² | 3 723 645 | 50 000 | 52 962 | 7.85 | 有大气 |
| Vall | `BODY-VALL` | Jool | 300 000 | 2.074 815×10¹¹ | 2 406 401 | 0 | 105 962 | 2.31 | |
| Tylo | `BODY-TYLO` | Jool | 600 000 | 2.825 280×10¹² | 10 856 518 | 0 | 211 926 | 7.85 | 无大气 |
| Bop | `BODY-BOP` | Jool | 65 000 | 2.486 834×10⁹ | 2 588 559 | 0 | 544 507 | 0.589 | |
| Pol | `BODY-POL` | Jool | 44 000 | 7.217 021×10⁸ | 2 042 599 | 0 | 901 903 | 0.373 | |
| Eeloo | `BODY-EELOO` | Kerbol | 210 000 | 7 441 083×10¹⁰ | 119 082 940 | 0 | 194 600 | 1.69 | |

> **数据来源声明**：以上常数取自 KSP 官方 Wiki（Kerbin/Mun/Minmus 等原版天体）交叉核对。文档中须标注「数值以 KSP 版本 1.12.x 为准；若游戏版本更新或使用 RSS/OPM 等天体模组，需重新采集」。`Body` 表设计为**可编辑**正是为此 —— 天体常数是数据而非硬编码。

### 9.2 验算样例（写入 `06`，用于单元测试）

> 下表的「期望输出」**已用 Python 实测验证过**（除标注「待测」者），可直接作为单元测试断言值。

| 验算项 | 输入 | 期望输出 | 实测 |
|---|---|---|---|
| Kerbin 同步轨道半长轴 | `mu=3.5316e12`, `sidereal_day=21549.4` | `a_sync ≈ 3 463 331 m`（高度 ≈ 2 863.33 km） | ✅ 回代周期 21 549.4 s，偏差 0.0000% |
| **同步轨道自洽性**（推荐主测试用例） | `a = 3463331`, `mu = 3.5316e12` | `T ≈ 21549.4 s` | ✅ 偏差 0.0000% |
| Mun 同步轨道自洽性 | `a = 3170557`, `mu = 6.513839e10` | `T ≈ 138 984 s`（= `sidereal_day`） | ✅ 偏差 0.0000% |
| Minmus 同步轨道自洽性 | `a = 417941`, `mu = 1.7658e9` | `T ≈ 40 400 s` | ✅ 偏差 0.0000% |
| 单级 Δv 手算 | `isp=345`, `m0=10 t`, `mf=4 t`, `g0=9.80665` | `Δv = 345×9.80665×ln(2.5) ≈ 3100.1 m/s` | ✅ 3100.1 m/s |
| 起飞推重比 | `thrust=200 kN × 4`, `m0=40 t`, `g=9.81` | `TWR ≈ 2.039` | ✅ 2.039 |
| 近/远拱点 | `a = 700000`, `e = 0.1` | `rp = 630 000 m`, `ra = 770 000 m` | 待测（公式直接） |
| **Kerbin 低轨周期**（推荐补入） | `sma = 700000`（即高度 100 km）, `mu = 3.5316e12` | `T ≈ 1958.1 s`（≈ 32.64 分钟） | ✅ 1958.1 s |
| Kerbin 大气层顶圆轨 | `sma = 670000`（高度 70 km） | `T ≈ 1833.6 s`（≈ 30.56 分钟） | ✅ 1833.6 s |
| 霍曼转移 Kerbin 100 km → Mun 轨道 | `路线 A=700000`, `路线 B=12000000`, `mu=3.5316e12` | `Δv1 ≈ 841.6`, `Δv2 ≈ 362.4`, 合计 `≈ 1204.0 m/s`；转移时间 `≈ 26750 s`（1.24 天） | ✅ 已实测 |

> **⚠️ 又一处我自己算错的算例（同类错误第 2 次）**：我最初在草稿里写「`a=700000` 的 Kerbin 低轨周期 ≈ 1837 s」，**这是错的**。
> 错因：把 `a = 600000 + 70000 = 670000`（**高度 70 km**，得 1833.6 s）的 `sma` 与「`a = 700000`」（**高度 100 km**，得 1958.1 s）混为一谈。
> **教训强化**：`sma` 是**轨道半长轴（天体中心到轨道）**，不是高度，两者相差一个 `Body.radius`（Kerbin 为 600 km）。所有算例必须显式写明是 `sma` 还是高度，**这是本项目计算层最容易出错的地方**，已同步写入 `06` 的警示框。

> **⚠️ 我最初起草时把「天体公转轨道半径」当成了 `sma` 代入公式，得出过错误的参考值。**
> 教训已写入 `06`：**`sma` 必须取「被天体环绕的轨道半长轴」，而公转轨道半径是另一个量。** 单元测试优先采用上表的「同步轨道自洽性」用例——它只需 `Body` 自身的 `mu` 与 `sidereal_day`，不存在量混用的空间。

---

## 10. 依赖与运行

### 10.1 `requirements.txt`（目标）

```
Django==5.2.*
numpy>=1.26
```

> 说明：Django ORM 已覆盖全部数据库访问，**不再需要 PyMySQL / WTForms / passlib**。
> - `WTForms` → Django Forms 替代
> - `passlib` → Django 内置 `PBKDF2` 密码哈希替代（旧项目用 `sha256_crypt`，Django 默认更安全）
> - `PyMySQL` → Django ORM 替代（SQLite 用内置驱动）

### 10.2 环境与命令

```powershell
# 一次性：创建环境（Python 3.10）
conda create -n rocket python=3.10 -y
conda activate rocket
pip install -r requirements.txt

# 初始化数据库
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata fixtures/bodies.json fixtures/parts_sample.json
python manage.py createsuperuser

# 运行
python manage.py runserver 127.0.0.1:8000
#   → 应用界面    http://127.0.0.1:8000/
#   → 管理后台    http://127.0.0.1:8000/admin/
```

**注意**：本机 PATH 上的 `python` 是 `D:\MinGW\bin\python.exe`（**无 Django**），**必须 `conda activate rocket` 后运行**。这是旧项目也存在的环境陷阱（旧项目须用 `OrionDB` 环境），写入 `07` 的「运行须知」。

### 10.3 `.gitignore` 增补
```
db.sqlite3
.env
__pycache__/
*.pyc
```

---

## 11. 新旧对照与迁移（`07-重构方案` 的依据）

### 11.1 表级对照矩阵

| 旧表/文件 | 新模型/文件 | 变更类型 | 数据迁移 |
|---|---|---|---|
| `Carrier`（11 字段） | `CarrierModel`（14 字段） | 改造 | 字段映射见下；**运力/质量/推力/推重比 4 字段废弃**（改由计算派生） |
| `Payload`（6 字段） | `PayloadModel`（13 字段） | 改造 | `Ptype` 文本 → `PayloadType` 枚举需人工映射 |
| `Site`（4 字段） | `Site`（12 字段） | 改造 | `Slatitude`/`Slongitude` `CHAR(6)`→`Float`；**新增必填 `body` 外键**，旧数据统一填 Kerbin |
| `SCP`（10 字段） | `FlightLog`（14 字段） | 改名改造 | `SCPdate DATE`→`actual_ut Float`（需换算）；`State` 文本→枚举 |
| `users` | `auth_user`（Django 内置） | 替换 | **密码哈希不兼容**（`sha256_crypt` vs Django PBKDF2）；旧用户需重置密码，或写一次性自定义 hasher |
| — | `Body` `PartCatalog` `FuelTank` `Engine` `ScienceInstrument` `Stage` `StageTank` `Program` `ProgramLink` `Spacecraft` | 新增 | 种子数据 + 手工录入 |
| `manage.py`（992 行 / 22 个 `@app.route`，含辅助函数共 26 个顶层定义） | `config/` + 9 个 app | 拆分 | 逻辑对照见 11.3 |
| `mysql_util.py`（103 行） | **删除** | 删除 | Django ORM 替代 |
| `forms.py`（292 行 / 5 个 Form） | `<app>/forms.py` | 重写 | 迁移到 Django Forms；**补上旧项目缺失的 `LaunchSiteForm` 校验** |
| `arock.sql` | `fixtures/*.json` + migrations | 替换 | 建表由 Django migrations 管理 |
| `random_generator/*.py`（4 个） | `management/commands/seed_*.py` | 改造 | 生成器思路保留，输出改为 Django fixture |
| `*_data.csv` / `*_data.sql` | — | 废弃 | KSP 数据改为真实部件种子数据 |
| `templates/`（20 个） | `templates/`（17 个页面） | 重写 | 字段全变，无法直接复用；布局 `layout.html`→`base.html` |

### 11.2 旧项目已知缺陷的修复清单（这是「重构」的实质内容）

| # | 旧缺陷 | 新方案 | 修复位置 |
|---|---|---|---|
| 1 | `index()` 查 `SCPForUser` 视图，但 `arock.sql` **未创建该视图** → 按 README 初始化后首页必崩 | Django 视图函数 + ORM 查询，**不依赖手工建视图**；需跨表数据处用 `select_related` | `core/views.py` |
| 2 | `forms.py` 定义了 `LaunchSiteForm` 但 `manage.py` **未导入**，发射场模块 `request.form.get()` 裸取值、无校验 | `SiteForm(ModelForm)` 统一校验，`SiteCreateView/UpdateView` 使用 | `sites/forms.py` |
| 3 | 全项目 SQL 字符串拼接（登录处 `WHERE username='%s'`）→ **SQL 注入** | Django ORM 参数化查询，**代码中不再出现裸 SQL** | 全项目 |
| 4 | `app.secret_key = "secret123"` 硬编码，且写在 `if __name__ == "__main__"` 内 | `settings/base.py` 中从环境变量读取，`dev.py` 用开发默认值；`.env` 不入库 | `config/settings/` |
| 5 | `app.run(debug=True)` 无环境区分 | `settings/dev.py` 与 `prod.py` 分离 | `config/settings/` |
| 6 | 删除走 **GET** `/delete_xxx/<id>`，无 CSRF → 可跨站触发 | Django `DeleteView`（仅 POST）+ CSRF 中间件默认开启 | 所有 `*_delete` |
| 7 | `MysqlUtil` 一次性实例（每方法 `finally: close()`）→ 视图里到处重复 `db = MysqlUtil()` | Django ORM 连接池/请求级连接管理 | 全项目 |
| 8 | 裸 `except` 只写 `log.txt` 不抛出，调用方拿到 `None` 引发 `TypeError` | 让异常传播，用 Django 日志配置；关键路径用 `transaction.atomic()` | 全项目 |
| 9 | `Slatitude/Slongitude` 为 `CHAR(6)`，**存不下负号+小数** | `FloatField` + 范围校验 | `sites/models.py` |
| 10 | `forms.py` 中 `Length(min=6, max=6)` 与 `arock.sql` 的 `CHAR(5)` **自相矛盾** | 废除定长编号，改 `code` 短码 + 正则校验 | 全项目 |
| 11 | 表名 `SCP`、字段 `SCPno/SCPname/SCPdate` 在 KSP 语境下无语义 | 改名 `FlightLog` / `code` / `name` / `planned_ut` / `actual_ut` | `launches/models.py` |
| 12 | 无任何测试 | `services/` 单元测试 + 表单校验测试 | `tests.py` |
| 13 | 无数据库迁移机制（`DROP DATABASE` 重建） | Django migrations 版本化 | `*/migrations/` |

### 11.3 `manage.py` 逻辑去向

| 旧函数（行号） | 新位置 |
|---|---|
| `index()` (22) | `core.views.HomeView` |
| `about()` (50) | `core.views.AboutView`（或并入首页页脚，v1 可省） |
| `is_logged_in()` (56) | Django `LoginRequiredMixin` |
| `carrier()` (69) | `carriers.views.CarrierListView`（筛选改 GET 查询参数，不再用 POST 搜索） |
| `add_carrier()` (95) | `carriers.views.CarrierCreateView` + `StageFormSet` |
| `edit_carrier()` (159) | `carriers.views.CarrierUpdateView` + `StageFormSet` |
| `delete_carrier()` (235) | `carriers.views.CarrierDeleteView` |
| `payload()` (265) | `payloads.views.PayloadListView` |
| `add_payload()` (289) / `edit_payload()` (339) / `delete_payload()` (404) | 对应 `payloads.views.*` + `StageFormSet` |
| `site()` (435) | `sites.views.SiteListView` |
| `add_site()` (457) / `edit_site()` (502) / `delete_site()` (563) | 对应 `sites.views.*`，**改用 `SiteForm` 校验** |
| `check_foreign_key()` (595) | 由数据库 `on_delete=PROTECT` 强制，**函数废弃** |
| `scp()` (601) | `launches.views.FlightListView` |
| `add_scp()` (656) / `edit_scp()` (749) / `delete_scp()` (848) | 对应 `launches.views.*` |
| `register()` (876) / `login()` (899) / `logout()` (936) | Django `auth`（`django.contrib.auth.urls` + 内置视图） |
| `dashboard()` (945) | `core.views.HomeView`（登录后看板）+ `programs.views.ProgramDetailView` |

### 11.4 数据迁移策略

**⚠️ 这是本次设计留下的一个「待用户裁决」项，不是已定决策。**

初稿推荐 路线 A（不迁移），我在复核 `arock.sql` 后一度改为推荐 路线 B，但 `07` 撰写者核实出 **CSV 里有 82 行真实地球航天数据**（21 行地球发射场、31 行中国航天器、31 行真实世界发射记录），该反驳成立 —— **我的判断只对 `arock.sql` 的 17 行成立，对 CSV 的 82 行不成立**。因此改为三条路线并列：

| 路线 | 做法 | 工作量 | 适合谁 |
|---|---|---|---|
| **路线 A · 不迁移** | 建新库 → `loaddata fixtures/bodies.json` → 手工录入 | ≈ 0.2 天 | 把本项目当**纯 KSP 工具**；旧记录对你无情感价值 |
| **路线 B · 全量迁移** | `migrate_legacy.py` 读旧 5 表**全量**映射 | ≈ 1.2 天 | 想完整保留旧台账（含 82 行真实地球数据），接受「Kerbin 上出现酒泉发射场」这类语义混杂 |
| **★ 路线 C · 混合** | 只迁 `arock.sql` 的 **17 行**（5 火箭 + 3 载荷 + 4 发射场 + 4 日志）；**跳过 CSV 的 82 行** | ≈ 0.5 天 | 想保留 KSP 主题的火箭与级配置，又不想污染 KSP 语境 |

**旧数据的真实构成**（详见 `07` §8.2 的完整数据画像）：

| 来源 | 行数 | KSP 相关？ |
|---|---|---|
| `arock.sql` 火箭（`Cconfig = "助推器：RT10,一级：T45+T1000"`） | 5 | ✅ 是（KSP 部件俗称） |
| `arock.sql` 载荷 / 发射场 / 日志 | 3 / 4 / 4 | ⚠️ 虚实混杂（日志含 `'kerbin-duna转移轨道_5:50圆轨'`） |
| `site_data.csv` | 20 | ❌ 全部是真实地球发射场 |
| `payload_data.csv` | 30 | ❌ 全部是真实中国航天器名（嫦娥IV、悟空II…） |
| `scp_data.csv` | 30 | ❌ 真实世界航天（含 1970 年等真实日期） |

**两条路的共识事实**（无分歧）：**级结构（`Stage`/`StageTank`）在任何路线下都无法自动完整重建** —— `Cconfig` 只是部件串文本，匹配到 `PartCatalog` 必须人工核对。差别在于 路线 B/路线 C 至少有部件串作为解析起点，路线 A 则完全从零录入。

**由此产生的完整理由**（原 路线 B 论证，仅对 `arock.sql` 的 17 行有效）：

1. 旧 `arock.sql` 是 KSP 语境的真实玩家风格数据（火箭名、级配置、Kerbin→Duna 发射记录都在）；
2. 数据量极小（5 火箭 / 3 载荷 / 4 发射场 / 4 日志）；
3. **旧 `Cconfig` 事实上已是 KSP 部件串**（`RT10`、`T45+T1000`），迁移时可顺带解析成 `Stage`/`StageTank` 的初稿 —— 若放弃数据则这段信息永久丢失；
4. 但 路线 B 全量迁移会把 82 行地球数据带入，产生语义污染（见 `07` §8.3）。

**因此我现在的建议是 路线 C**：兼顾「保留优质 KSP 数据」与「不污染语境」，成本仅比 路线 A 多 0.3 天。

**下表适用于 路线 B 与 路线 C**（两者都要处理 `arock.sql` 的 `State` 文本）：

**旧 `State` 文本 → `FlightState` 枚举映射建议表**（依据 `arock.sql` 与 `scp_data.csv` 的实际取值）：

| 旧文本值 | 出现位置 | 映射为 | 说明 |
|---|---|---|---|
| `正常` | `arock.sql` 第 74、75 行 | `LAUNCHED` | 发射正常执行 |
| `成功` | `scp_data.csv` | `LAUNCHED` | 同义，成功执行（旧数据把「成功」记在 `State` 而非结果字段） |
| `失败` | `arock.sql` 第 76 行 | `FAILED` | 发射失败 |
| `结束` | `arock.sql` 第 77 行 | `LAUNCHED` + `result_code=0` | 「结束」表示任务已完结，语义上等同成功完成；若原意为「已终止」则映射 `CANCELLED`，**需人工判定** |
| 其他/空 | — | `PLANNED` | 兜底 |

**路线 B 的其余映射规则**：
- `SCPdate DATE`（如 `'1999/3/6'`）→ `actual_ut Float`：DATE 无游戏时间语义，**需人工指定换算基准**（建议：按日期序号 × 21600 s 伪映射，并在 `detail` 中保留原日期文本，避免伪造精度）。
- `Cmaiden DATE` → `first_flight_ut`：同上。
- `Slatitude '40.00N'` / `Slongitude '100.0E'` → `latitude 40.0` / `longitude 100.0`：解析方位后缀，`S`/`W` 取负。
- 旧用户密码（`sha256_crypt`）与 Django 默认 PBKDF2 哈希**不兼容**：迁移时置为不可用密码，要求重置；或写一个一次性自定义 hasher 校验旧哈希并在首次登录时升级。
- 旧 `Ptype` 文本（`载人仓`/`探测器`/`实验仓`）→ `PayloadType` 枚举，需人工映射表。

**路线 A 的适用情形**：若你确认这些数据只是当年交作业用的、不值得保留，则 路线 A 更省事。

---

## 12. 文档依赖与撰写顺序

```
_design-brief.md（本文，唯一权威源）
   │
   ├─► 01-需求规格说明.md ⭐含技术选型论证
   │      │
   │      └─► 02-概念模型.md ⭐含术语映射与ER图
   │             │
   │             └─► 03-数据库设计.md ⭐含字段定义与约束   ← 数据模型在此冻结
   │                    │
   │                    ├─► 04-接口与路由设计.md
   │                    │      │
   │                    │      └─► 05-页面交互设计.md
   │                    │
   │                    ├─► 06-核心计算设计.md（数学部分独立，依赖 02/03）
   │                    │
   │                    └─► 07-重构方案与实施计划.md ⭐新旧对照
   │                           │
   │                           └─► 08-任务清单.md（WBS，可勾选）
```

**约束**：`03` 冻结数据模型之后，`04`/`05`/`06`/`07` 不得再引入字段级变更；若确需变更，回改 `03` 与本文（`_design-brief.md`）后再推进。

---

## 13. 实施阶段划分（`08-任务清单` 的骨架）

| 阶段 | 内容 | 依赖 | 验收标准 |
|---|---|---|---|
| **P0 地基** | conda 环境 `rocket`、`config/` 拆分 settings、`requirements.txt`、`.gitignore`、Django 项目骨架、`core` app 与 `Body` 模型、`fixtures/bodies.json`、`services/orbital.py` + 单测 | — | `manage.py runserver` 可启动；`/admin/` 可登录；`Body` 17 条种子数据可见；`orbital` 单测通过（含 Kerbin 同步轨道验算） |
| **P1 部件库** | `parts` 全部 4 模型 + Admin + 列表/详情页 + 部件种子数据 | P0 | 可在 Admin 录入燃料罐/引擎/科学设备；部件列表按类型筛选正常 |
| **P2 载具与级** | `carriers`/`payloads`/`sites` + `stages`（`Stage`+`StageTank`）+ `StageFormSet` + `stage_formset.js` 动态增删 + `services/deltav.py` + 单测 | P1 | 能建一枚含 ≥3 级、每级挂 ≥2 种燃料罐的火箭；详情页显示逐级 Δv 累加与起飞 TWR；Δv 单测通过 |
| **P3 发射与计划** | `launches`（`FlightLog` + 发射日程页 + 一键执行发射）+ `programs`（`Program`+`ProgramLink` + 计划总览页）+ `services/stats.py` | P2 | 「安排——发射——记录」闭环可用；计划总览能按 `object_type` 聚合展示全部成员；`ProgramLink` 的 CHECK 约束在越界写入时报错 |
| **P4 在轨与统计** | `spacecraft`（`Spacecraft` + 轨道表单 + AJAX 周期计算）+ 首页看板 + 统计聚合 | P2 | 航天器录入后实时显示周期/近远拱点；首页显示近期发射与进行中计划 |

---

## 14. 待确认与风险登记

| # | 项 | 状态 | 影响 |
|---|---|---|---|
| R-01 | KSP 天体常数的版本适用性（1.12.x 为准） | 已声明 | 使用 RSS/OPM 模组时需重新采集；`Body` 表可编辑即为此预留 |
| R-02 | `FUEL_UNIT_MASS = 0.005 t/单位` 为混合平均简化 | 已声明 | Δv 计算有系统性偏差（量级正确）；`06` 须标注为已知简化 |
| R-03 | 两级 FormSet 嵌套（火箭→级→燃料罐）实现复杂度 | 待验证 | 有降级方案（见 7.1 第 5 条），已写入 `08` 可选项 |
| R-04 | 旧用户密码哈希不兼容 | 已声明 | 选 路线 A 则不涉及；选 路线 B 需重置密码 |
| R-05 | Django Admin 多态内联限制 | 已规避 | 用两个独立 `TabularInline` 替代 `GenericTabularInline`（见 5.3） |
| R-06 | 单机自用，未做并发/权限/部署硬化 | 已知 | 超出 v1 范围；`prod.py` 留占位 |
| R-07 | **数据迁移路线（路线 A/路线 B/路线 C）尚未由用户裁决**（见 11.4）。初稿推荐 路线 A、我改为 路线 B、`07` 以 CSV 的 82 行地球数据反驳成立 → 现推荐 **路线 C 混合路线**，但需用户确认 | **待用户裁决** | 影响 `07` §8 与 `08` 中是否有 `migrate_legacy.py` 任务；不阻塞 P0–P2 |
| R-08 | **Mun 与 Moho 的同步轨道半长轴超出各自 SOI 半径**（Mun `a_sync = 3 170 557 m` > SOI `2 429 559 m`；Moho `18 423 162 m` > SOI `9 640 781 m`） | 已知（`06` 已记录） | 数值计算正确但物理不可实现 → 展示层须做 SOI 越界警告，不可当作异常 |
| R-09 | **`ProgramLink.spacecraft` 使 `programs` 依赖 `spacecraft`** → 迁移顺序受限 | 已知（`03`/`08` 已处置） | 迁移链为 `core → parts → carriers/payloads → stages/sites/launches → spacecraft → programs`；`08` 已插入前置任务 `P3-pre1` |
| R-10 | **`stage_reorder` 批量重排会撞唯一约束** | 已知（`04`/`05`/`08` 已处置） | 不能用负数临时序号（`stage_order >= 1` 的 CHECK 会拒绝）→ 用「现有最大值 + 偏移」的临时区间 |

---

*本文为内部基准，任何字段或约束的变更必须在此先行修改，再同步至对应交付文档。*

---

## 15. 修订日志（Revision Log）

### v1.1 — 2026-09-19（08 份交付文档完成后的一致性复核）

08 份文档的撰写者独立核对了本文，指出若干**真实错误**。以下为本次修正项，均已在正文落实：

| # | 修正项 | 性质 | 发现者 |
|---|---|---|---|
| 1 | **`stage_order` 方向约定缺失** → 新增权威定义（`1` = 最先点火/最下方一级，向上递增；页面按降序自上而下渲染；Δv 从 1 开始累加） | **规范缺口**（最严重，影响 03/05/06 三份文档） | `03`/`05` 双方独立提出 |
| 2 | `Body.Meta.ordering` 引用**幽灵字段 `depth_hint`** → 改为 `['sort_order', 'name']`，层级缩进改用计算属性 `Body.depth` | 字段不存在 | `01`/`03`/`04`/`08` 四份独立发现 |
| 3 | 4.3 容量语义**自相矛盾**（先写「1 单位 ≈ 1 kg」后写「5 kg」）→ 删除错误读法，并补入 FL-T800/T400/T200 反推实证 | 内部矛盾 | `01`/`03` |
| 4 | 9.1 天体表 **Bop/Pol 的 `mu` 漏小数点**（排版损伤，数值放大 1000 倍）→ `2.486 834×10⁹` / `7.217 021×10⁸` | **数值错误** | `03` |
| 5 | 4.6 `Cconfig` 同时出现在「语义扩展」与「被移除字段」→ 从移除清单移出 | 内部矛盾 | `03` |
| 6 | 第 6 节根路由表**漏列 `stages/`**（而 6.1 定义了 4 条 `/stages/…`）→ 补入 | 遗漏 | `04`/`08` |
| 7 | 4.16 删除策略表**漏 `Body → Program.target_body`（SET_NULL）** → 补入 | 遗漏 | `03` |
| 8 | 4.15 `code` 口径不一（「每张业务表」列 8 张 vs 「另设 code」）→ 明确为 **11 张表带 `code`**，含 3 张部件子表 | 口径不一 | `01`/`03` |
| 9 | `eccentricity` 约束与 `ESCAPING` 逃逸轨道**无法共存** → 定死：DB 只校验 `e >= 0`，`clean()` 按 `situation` 分级校验，`e >= 1` 时周期返回 `None` | 规范冲突 | `01`/`03` |
| 10 | 未显式说明含 `code` 的模型**一律继承 `CodeModel`** → 补入 4.0 全局约定 | 规范缺口 | `04`/`08` |
| 11 | `CodeModelMixin` / `CodeModel` 命名不一 → 统一为 **`CodeModel`** | 命名不一 | `03` |
| 12 | 文件规模与计数错误：`forms.py` 255→**292** 行、`mysql_util.py` 96→**103** 行、`manage.py`「26 路由」→**22 个 `@app.route`**（26 是顶层定义数） | 事实错误 | `04`/`07` |
| 13 | 4.10 旧 `CHAR(6)` 坐标的论证不准确（旧数据实为 `'28.56N'` 半球后缀，**并未溢出**）→ 改为三条真实缺陷：精度被字母挤占、无法改用负号格式、非数值无法做几何计算 | 论证不准确 | `07` |
| 14 | 11.4 迁移建议反复更正：初稿推荐 路线 A → 我改为推荐 路线 B → **`07` 撰写者以 CSV 的 82 行真实地球数据反驳，其反驳成立**。最终**改为三条路线并列（路线 A/路线 B/路线 C），推荐 路线 C 混合路线，交由用户裁决** | **判断更正（含我的一次误判）** | 我与 `07` 撰写者往复复核 |
| 15 | 9.2 我自己的两处算例错误（同步轨道值、Kerbin 低轨周期 `a` vs 高度混淆）→ 已修正并加双警示框 | **计算错误** | 我自己用代码验算发现 |
| 16 | **迁移路线编号与 `08` 的里程碑/风险编号撞车**：初稿用 `M1/M2/M3`（与 `08` 的里程碑 M1/M2/M3 冲突），改 `R1/R2/R3` 后又与 `08` 的风险 `R-01`~`R-10` 冲突 → 最终统一为**「路线 A/B/C」**，全量改名（基准 33、`03` 18、`07` 74、`01` 8 处） | **自造冲突** | 我在复核 `08` 时发现（同一文档内两套含义） |
| 17 | `02`/`03`/`01`/`07` 正文中残留的「7 个 app」计数与「`manage.py` 26 条路由」→ 已改为 9 个 app / 22 个 `@app.route` | 计数不实 | 我复核时发现 |
| 18 | `01`/`08` 的验收断言仍沿用**错误周期值 1837 s** → 改为 1958.1 s，并注明 1837 对应 70 km 高度 | **计算错误传播** | `06` 的勘误表 + 我复核时发现 |
| 19 | `03` 两处仍保留基准初稿的「1 单位 ≈ 1 kg」错误读法 → 已删除 | 内部矛盾传播 | 我复核时发现 |

**本次复核中我犯的错误（如实记录，供后续参考）**

| 错误 | 性质 | 教训 |
|---|---|---|
| 把「天体公转轨道半径」当 `sma` 代入周期公式 | 物理量混淆 | `sma` 是轨道半长轴，不是高度、也不是公转半径；三者相差 `Body.radius` 或整个量级 |
| 把「`a=700000` 的周期」写成 1837 s | 同上（`a` 与高度混淆） | 所有轨道算例必须显式写明是 `sma` 还是高度 |
| 复核 `arock.sql` 后把迁移建议从「推荐 M1」改为「推荐 M2」，忽略了 CSV 的 82 行数据 | 证据取样不全 | 只看了 `arock.sql` 就下结论；`07` 撰写者读了 CSV 才对 |
| 迁移路线先用 `M1/M2/M3`、后改 `R1/R2/R3` | 命名未先查全局 | 新增编号体系前必须先 grep 全项目既有编号 |

**尚未在本文修改、但需下游统一的技术细节**（属实现技巧，不影响模型）：

| # | 事项 | 决定 |
|---|---|---|
| D-14 | `CheckConstraint` 的关键字参数 | **统一用 `condition=`**（Django 5.1+ 官方参数，`check=` 是旧名）。`03`/`04` 已按 `condition=` 撰写，无需改动 |
| D-15 | `StageReorderView` 两阶段重排的临时序号 | **不能用负数**（`stage_order__gte=1` 的 CHECK 会拒绝）→ 改用「现有最大值 + 偏移」的临时区间 |
| D-16 | FormSet 中读取 `form.cleaned_data` | `add_error()` 之后该属性为 `None`，必须加守卫，否则 `AttributeError` |
| D-17 | Kerbol 的 `soi_radius` | JSON fixture 中填 `null`（不能写 `∞`）；恒星的影响球无物理意义 |
| D-18 | `programs` 的迁移顺序 | `ProgramLink.spacecraft` 使其依赖 `spacecraft` → 迁移链为 `core → parts → carriers/payloads → stages/sites/launches → spacecraft → programs`；`programs` 的 `0001_initial` **是最后一个** |
| D-19 | `FlightLog.rest_dv` 可空性 | **可空**（NULL = 未记录），以区分「剩余 Δv 为 0」与「未记录」；旧表 `NOT NULL` + `0` 混淆了二者 |
| D-20 | `ProgramLink` 的成员加入顺序 | 先建 `spacecraft` 再建 `programs`（同 D-18），或在 `ProgramLink` 中把 `spacecraft` FK 放到后一个 migration |
| D-21 | 换库到 MySQL 时需手动加 CHECK | Django 在 SQLite 上通过 `CheckConstraint` 建约束；迁移到 MySQL 8.4 时同样支持，但需 `dumpdata`/`loaddata` 搬数据 |
| **D-22** | **迁移路线编号（本条由复核时的一次自造冲突得出）** | **统一为「路线 A / 路线 B / 路线 C」**（A=不迁移、B=全量迁移、C=混合迁移）。**⚠️ 不得使用 `M1`/`M2`/`M3` 或 `R1`/`R2`/`R3`** —— `08-任务清单.md` 已用 `M1/M2/M3` 作**里程碑**编号、用 `R-01`~`R-10` 作**风险**编号；本基准初稿先用 `M1/M2/M3`、后改 `R1/R2/R3`，**两次都与 `08` 的既有编号撞车**，最终改用中文「路线」前缀方可无歧义。已全量改名（基准 33 处、`03` 18 处、`07` 74 处、`01` 8 处） |
| D-23 | 「26 个路由」这一说法 | 作废。旧 `manage.py` 实为 **22 个 `@app.route`**；「26」是 22 路由 + `is_logged_in` + `check_foreign_key` + 内层 `wrap` + `__main__` 块的**顶层定义数**。全套文档改口径为「22 个 `@app.route` / 26 个顶层定义」 |
