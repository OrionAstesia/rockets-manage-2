# 数据模型与数据库

> **这是数据模型的唯一权威定义。** 字段名、类型、约束、枚举、`on_delete` 全部以本文为准。
> 改造前先改本文。设计理由见 `docs/archive/`（不需要读也能开发）。

- 数据库：**SQLite**（`db.sqlite3`，单文件，可直接拷贝备份）
- 建模方式：**Django 5.2 ORM + migrations**（不写裸 SQL DDL）
- 规模：**14 张表，9 个 app**
- 主键：全部 `BigAutoField`（`DEFAULT_AUTO_FIELD` 设为 `django.db.models.BigAutoField`）

| app | 表 |
|---|---|
| `core` | `Body` |
| `parts` | `PartCatalog`、`FuelTank`、`Engine`、`ScienceInstrument` |
| `carriers` | `CarrierModel` |
| `payloads` | `PayloadModel` |
| `stages` | `Stage`、`StageTank` |
| `sites` | `Site` |
| `launches` | `FlightLog` |
| `programs` | `Program`、`ProgramLink` |
| `spacecraft` | `Spacecraft` |

---

## 0. 全局约定

| 项 | 约定 |
|---|---|
| 命名 | Python 字段 `snake_case`，类名 `PascalCase`，表名 Django 默认 `app_model` 小写 |
| 所有字段 | 必须带 `verbose_name`（中文）；`Meta.verbose_name` / `verbose_name_plural` 必须中文；易错字段带 `help_text` |
| 主键 | 统一 `id = BigAutoField` |
| 业务短码 | **11 张表带 `code` 字段**（见 §3） |
| 时间 | **KSP 游戏时间 `UT`**（游戏内秒，`FloatField`）。**不用 `DateField`/`DateTimeField` 存游戏时间** |
| 质量 | 吨（t），`FloatField` |
| 推力 | 千牛（kN），`FloatField` |
| 比冲 | 秒（s），`FloatField` |
| 距离 | 米（m），`FloatField` |
| 角度 | 度（°），`FloatField`（倾角 0–180，其余 0–360） |
| 造价 | 根币（√），`PositiveIntegerField` |
| 审计字段 | 除 `Body`/`PartCatalog` 外，业务表加 `created_at`/`updated_at`（`auto_now_add`/`auto_now`，**现实世界时间**，仅用于管理） |
| 软删除 | v1 不用 |

### 0.1 模型基类（`core/mixins.py`）

```python
CODE_RE = r"^[A-Z0-9][A-Z0-9/\-]{1,22}[A-Z0-9]$"


class CodeModel(models.Model):
    """所有带业务短码的模型的基类。11 张表继承它。"""
    code = models.CharField(
        "代号", max_length=24, unique=True, db_index=True,
        validators=[RegexValidator(CODE_RE, "代号格式：大写字母/数字，可用 - 或 /，总长 3–24")],
    )

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True
```

### 0.2 约束的分工（重要）

| 类型 | 放哪里 | 为什么 |
|---|---|---|
| 单表、同表字段之间的规则 | **DB `CheckConstraint`** | 数据层强制，Admin/脚本/shell 都拦得住 |
| 跨表规则（如 `FuelTank.wet_mass >= part.dry_mass`） | **模型 `clean()`** | **SQLite 的 CHECK 不支持子查询**，无法引用其他表 |
| 需要友好中文提示的业务规则（如 `FlightLog` 状态-时间一致性） | **模型 `clean()`**（可 DB CHECK 兜底） | DB 报错信息对玩家不可读 |

> 用 `CheckConstraint(condition=...)`。**Django 5.1+ 的官方关键字是 `condition=`**，`check=` 是旧名。

---

## 1. 枚举（`TextChoices`，全部用文本枚举便于阅读）

放在各自 app 的 `models.py` 顶部（或用 `constants.py`）。

```python
class PartType(models.TextChoices):        # parts
    TANK = "TANK", "燃料罐"
    ENGINE = "ENGINE", "引擎"
    SCIENCE = "SCIENCE", "科学设备"
    OTHER = "OTHER", "其他结构件"

class FuelType(models.TextChoices):
    LF_OX = "LF_OX", "液体燃料+氧化剂"
    MONO = "MONO", "单元推进剂"
    XENON = "XENON", "氙气"
    SOLID = "SOLID", "固体燃料"
    ORE = "ORE", "矿石"
    OTHER = "OTHER", "其他"

class EngineCycle(models.TextChoices):
    GAS_GENERATOR = "GAS_GENERATOR", "燃气发生器"
    STAGED_COMBUSTION = "STAGED_COMBUSTION", "分级燃烧"
    EXPANDER = "EXPANDER", "膨胀循环"
    PRESSURE_FED = "PRESSURE_FED", "挤压式"
    SOLID = "SOLID", "固体"
    JET = "JET", "喷气"
    NUCLEAR = "NUCLEAR", "核热"
    MONO = "MONO", "单元推进剂"
    OTHER = "OTHER", "其他"

class PayloadType(models.TextChoices):     # payloads
    CREW_CAPSULE = "CREW_CAPSULE", "载人舱"
    CARGO = "CARGO", "货运舱"
    SATELLITE = "SATELLITE", "卫星"
    PROBE = "PROBE", "探测器"
    LANDER = "LANDER", "着陆器"
    STATION_MODULE = "STATION_MODULE", "空间站模块"
    ROVER = "ROVER", "巡视器"
    OTHER = "OTHER", "其他"

class StageOwnerType(models.TextChoices):  # stages
    CARRIER = "CARRIER", "火箭"
    PAYLOAD = "PAYLOAD", "载荷"

class SeparationType(models.TextChoices):
    STACK_DECOUPLER = "STACK_DECOUPLER", "堆叠分离器"
    RADIAL_DECOUPLER = "RADIAL_DECOUPLER", "径向分离器"
    DOCKING = "DOCKING", "对接分离"
    NONE = "NONE", "不分离"
    OTHER = "OTHER", "其他"

class MountPosition(models.TextChoices):
    INLINE = "INLINE", "堆叠"
    RADIAL = "RADIAL", "径向挂载"

class FlightState(models.TextChoices):     # launches
    PLANNED = "PLANNED", "计划中"
    COUNTDOWN = "COUNTDOWN", "发射准备"
    LAUNCHED = "LAUNCHED", "已发射"
    FAILED = "FAILED", "发射失败"
    CANCELLED = "CANCELLED", "已取消"

class ProgramStatus(models.TextChoices):   # programs
    PLANNED = "PLANNED", "规划中"
    ACTIVE = "ACTIVE", "进行中"
    COMPLETED = "COMPLETED", "已完成"
    CANCELLED = "CANCELLED", "已取消"

class ProgramObjectType(models.TextChoices):
    CARRIER = "CARRIER", "火箭"
    PAYLOAD = "PAYLOAD", "载荷"
    FLIGHT = "FLIGHT", "发射日志"
    SITE = "SITE", "发射场"
    SPACECRAFT = "SPACECRAFT", "航天器"

class Situation(models.TextChoices):       # spacecraft
    LANDED = "LANDED", "已着陆"
    SPLASHED = "SPLASHED", "水面溅落"
    FLYING = "FLYING", "大气内飞行"
    ORBITING = "ORBITING", "环绕轨道"
    ESCAPING = "ESCAPING", "逃逸中"
    DOCKED = "DOCKED", "已对接"
    DESTROYED = "DESTROYED", "已损毁"
```

---

## 2. 物理常数（`core/constants.py`）

```python
G0 = 9.80665            # 标准重力加速度 (m/s²)。Δv 公式用，与所在天体无关（详见 docs/spec/03 §1）
FUEL_UNIT_MASS = 0.005  # 每单位燃料质量 (t/单位)，即 1 单位 = 5 kg
KERBIN_DAY = 21600.0    # KSP 太阳日 (s)，仅用于展示层「天」换算
```

**`FUEL_UNIT_MASS` 的实证**：`(wet_mass − dry_mass) / 0.005 = capacity` 在三个原版燃料罐上精确吻合 —— FL-T800 `(4.5−0.5)/0.005 = 800`、FL-T400 `= 400`、FL-T200 `= 200`。所以这不是估算值，与 KSP 官方容量系统自洽。

---

## 3. `code` 业务短码规范

| 项 | 规范 |
|---|---|
| 正则 | `^[A-Z0-9][A-Z0-9/\-]{1,22}[A-Z0-9]$`（总长 3–24，大写） |
| 格式 | `前缀-主体[-序号]` |
| 前缀 | `BODY-` 天体 ｜ `PART-` 部件 ｜ `TANK-` 燃料罐 ｜ `ENG-` 引擎 ｜ `SCI-` 科学设备 ｜ `LV-` 火箭 ｜ `PL-` 载荷 ｜ `PAD-` 发射场 ｜ `SCP-` 发射日志 ｜ `PRG-` 计划 ｜ `S/C-` 航天器 |
| 示例 | `LV-DAVY2B`、`ENG-AJ10-37`、`PAD-KSC-LC1`、`SCP-2026-014`、`PRG-DUNA-01`、`S/C-KERBIN-SAT1` |
| 带 `code` 的 11 张表 | `Body`、`PartCatalog`、`FuelTank`、`Engine`、`ScienceInstrument`、`CarrierModel`、`PayloadModel`、`Site`、`FlightLog`、`Program`、`Spacecraft` |

> `FlightLog` 的 `SCP-` 前缀**刻意保留**（沿用旧系统的任务编号习惯）。

---

## 4. 表定义

### 4.1 `core.Body` — 天体

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 天体代号 |
| `name` | CharField(60) | unique | 天体名称 |
| `name_en` | CharField(60) | blank | 英文名 |
| `parent` | FK(self) | null, blank, **PROTECT**, related_name=`children` | 母天体 |
| `radius` | FloatField | null, blank | 赤道半径 (m) |
| `mu` | FloatField | null, blank | 标准重力参数 (m³/s²) |
| `soi_radius` | FloatField | null, blank | 影响球半径 (m) |
| `atmosphere_height` | FloatField | default=0 | 大气高度 (m) |
| `has_atmosphere` | BooleanField | default=False | 有大气 |
| `sidereal_day` | FloatField | null, blank | 恒星日 (s) |
| `solar_day` | FloatField | null, blank | 太阳日 (s) |
| `surface_gravity` | FloatField | null, blank | 表面重力 (m/s²) |
| `is_star` | BooleanField | default=False | 是恒星（Kerbol） |
| `is_reachable` | BooleanField | default=True | 可达 |
| `sort_order` | PositiveIntegerField | default=0 | 显示排序 |
| `description` | TextField | blank | 备注 |

- `Meta.ordering = ["sort_order", "name"]`
- **不继承 `CodeModel`**（无正则需求）但有 `code` 字段；实现时直接声明字段即可。
- **层级缩进用计算属性**，不落库：
  ```python
  @property
  def depth(self):
      d, p = 0, self.parent
      while p is not None:
          d += 1
          p = p.parent
      return d
  ```
  天体仅 17 条，Python 遍历零成本；**不要用递归 CTE**（SQLite 支持有限）。
- **约束**：`CheckConstraint(condition=Q(parent__isnull=True) | ~Q(parent_id=F("id")), name="body_no_self_parent")`（禁止自己当自己的母天体）。

### 4.2 `parts.PartCatalog` — 部件目录（超类）

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

- `Meta.indexes = [Index(fields=["part_type", "diameter"])]`（按类型+直径筛选适配性）
- `is_radial` / `stackable` 留在超类：它们是所有部件类型的安装共性。

### 4.3 `parts.FuelTank` — 燃料罐（需求①）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `part` | OneToOneField(PartCatalog) | **CASCADE**, related_name=`fuel_tank` | 对应部件 |
| `wet_mass` | FloatField | — | 满载质量 (t) |
| `capacity` | FloatField | — | 燃料容量 (单位) |
| `fuel_type` | CharField(12) | choices=`FuelType` | 燃料类型 |
| `usable_capacity` | FloatField | null, blank | 可用容量 (单位) |
| `is_jet` | BooleanField | default=False | 喷气燃料罐 |
| `note` | TextField | blank | 备注 |

- **约束**：`CheckConstraint(condition=Q(capacity__gte=0), name="fueltank_capacity_nonneg")`
- **`clean()`**：`wet_mass >= part.dry_mass`（跨表规则，见 §0.2）
- **⚠️ 容量语义**：`capacity` = **燃料资源单位数**，质量换算恒定用 `FUEL_UNIT_MASS = 0.005 t/单位`（1 单位 = 5 kg）。
  - `LF_OX`：`capacity` 为 **LF + OX 合计**单位，统一按混合平均质量折算（**不做 LF/OX 分账**，见 `docs/spec/03` §5 的简化说明）
  - `SOLID`：`capacity` 直接是固体燃料的质量换算单位，乘同一系数

### 4.4 `parts.Engine` — 引擎（需求②）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `part` | OneToOneField(PartCatalog) | **CASCADE**, related_name=`engine` | 对应部件 |
| `series` | CharField(60) | blank, db_index | 引擎系列 |
| `derived_from` | FK(self) | null, blank, **SET_NULL**, related_name=`variants` | 改进自 |
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
| `ignitions` | PositiveIntegerField | default=1 | 点火次数（**0 = 无限**） |
| `is_vacuum_optimized` | BooleanField | default=False | 真空优化 |
| `note` | TextField | blank | 备注 |

- **约束**：
  ```python
  CheckConstraint(condition=Q(thrust_asl__gte=0) & Q(thrust_vac__gte=0), name="engine_thrust_nonneg")
  CheckConstraint(condition=Q(min_throttle__gte=0) & Q(min_throttle__lte=100), name="engine_min_throttle_range")
  ```
- **`clean()`**：`thrust_vac >= thrust_asl`
- **`series` + `derived_from` 取代了「引擎族表」**：`AJ10`、`LV-909` 这类分组写进 `series` 列；变体血缘用 `derived_from`。

### 4.5 `parts.ScienceInstrument` — 科学设备（需求③）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `part` | OneToOneField(PartCatalog) | **CASCADE**, related_name=`science_instrument` | 对应部件 |
| `experiment_type` | CharField(40) | — | 实验类型 |
| `data_value` | FloatField | default=0 | 基础科学数据量 (Mits) |
| `is_repeatable` | BooleanField | default=False | 可重复使用 |
| `requires_crew` | BooleanField | default=False | 需要乘员 |
| `requires_surface` | BooleanField | default=False | 需要着陆/地表 |
| `transmit_efficiency` | FloatField | default=100 | 传输效率 (%) |
| `has_storage` | BooleanField | default=False | 自带数据存储 |
| `storage_capacity` | FloatField | default=0 | 数据存储容量 (Mits) |
| `note` | TextField | blank | 备注 |

- **`clean()`**：`0 <= transmit_efficiency <= 100`

### 4.6 `carriers.CarrierModel` — 运载火箭型号

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 火箭代号 |
| `name` | CharField(80) | unique | 火箭名称 |
| `series` | CharField(60) | blank, db_index | 系列 |
| `derived_from` | FK(self) | null, blank, **SET_NULL**, related_name=`variants` | 改进自 |
| `manufacturer` | CharField(60) | blank | 制造商 |
| `diameter` | FloatField | null, blank | 最大直径 (m) |
| `height` | FloatField | null, blank | 总高 (m) |
| `first_flight_ut` | FloatField | null, blank | 首飞时间 (UT) |
| `crew_capacity` | PositiveIntegerField | default=0 | 乘员容量 |
| `cost` | PositiveIntegerField | default=0 | 造价 (√) |
| `is_reusable` | BooleanField | default=False | 可回收复用 |
| `max_payload_mass` | FloatField | null, blank | 设计最大载荷 (t) |
| `description` | TextField | blank | 设计说明 |
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

> **`max_payload_mass` 是玩家声明的设计目标，不是计算结果。** 界面上与 `services/deltav` 算出的运力**并列显示**，不一致时给提示。不要用它做 Δv 计算。
>
> **刻意不设的字段**：LEO 运力、GTO 运力、箭体总质量、最大推力、推重比 —— 这些都能从 `Stage` + `StageTank` + `Engine` **算出来**，手工再录一份一定会与级配置漂移。

### 4.7 `payloads.PayloadModel` — 有效载荷型号

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 载荷代号 |
| `name` | CharField(80) | unique | 载荷名称 |
| `series` | CharField(60) | blank, db_index | 系列 |
| `derived_from` | FK(self) | null, blank, **SET_NULL**, related_name=`variants` | 改进自 |
| `payload_type` | CharField(20) | choices=`PayloadType` | 载荷类型 |
| `mass` | FloatField | default=0 | 载荷质量 (t) |
| `diameter` | FloatField | null, blank | 最小整流罩直径 (m) |
| `crew_capacity` | PositiveIntegerField | default=0 | 乘员容量 |
| `science_capacity` | FloatField | default=0 | 科学数据容量 (Mits) |
| `has_docking_port` | BooleanField | default=False | 带对接端口 |
| `cost` | PositiveIntegerField | default=0 | 造价 (√) |
| `instruments` | TextField | blank | 搭载仪器说明 |
| `description` | TextField | blank | 说明 |
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

### 4.8 `stages.Stage` — 级（需求⑥）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `owner_type` | CharField(10) | choices=`StageOwnerType` | 所属类型 |
| `carrier` | FK(CarrierModel) | null, blank, **CASCADE**, related_name=`stages` | 所属火箭 |
| `payload` | FK(PayloadModel) | null, blank, **CASCADE**, related_name=`stages` | 所属载荷 |
| `stage_order` | PositiveIntegerField | — | 级序号 |
| `name` | CharField(60) | blank | 级名称 |
| `engine` | FK(Engine) | null, blank, **PROTECT**, related_name=`stages` | 主引擎 |
| `engine_count` | PositiveIntegerField | default=1 | 引擎数量 |
| `is_radial_engine` | BooleanField | default=False | 引擎径向安装 |
| `separation_type` | CharField(16) | choices=`SeparationType`, blank | 分离方式 |
| `decoupler_mass` | FloatField | default=0 | 分离件质量 (t) |
| `has_fairing` | BooleanField | default=False | 此级带整流罩 |
| `min_throttle_used` | FloatField | null, blank | 实际使用的节流上限 (%) |
| `note` | TextField | blank | 备注 |
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

**约束（照抄，不要改）**：

```python
class Meta:
    ordering = ["stage_order"]
    constraints = [
        CheckConstraint(
            condition=(
                Q(owner_type="CARRIER", carrier__isnull=False, payload__isnull=True)
                | Q(owner_type="PAYLOAD", payload__isnull=False, carrier__isnull=True)
            ),
            name="stage_exactly_one_owner",
        ),
        UniqueConstraint(fields=["carrier", "stage_order"], name="uniq_carrier_stage_order"),
        UniqueConstraint(fields=["payload", "stage_order"], name="uniq_payload_stage_order"),
        CheckConstraint(condition=Q(stage_order__gte=1), name="stage_order_positive"),
        CheckConstraint(condition=Q(engine_count__gte=1), name="stage_engine_count_positive"),
    ]
```

**⚠️ `stage_order` 方向约定（全项目唯一权威，`05`/`06` 的实现必须与之一致）**

| | 约定 |
|---|---|
| `stage_order = 1` | **最先点火、位于最下方的那一级**（起飞级） |
| 递增方向 | 向上递增，最大值 = 最上一级（接近载荷） |
| 依据 | 与 KSP 游戏内建堆栈分离组编号一致（空格键触发的第一个分离事件就是「第 1 级」） |
| **页面渲染** | 按 `stage_order` **降序自上而下**（最上级在表格顶部、第 1 级在底部），与火箭外观一致 |
| **Δv 计算** | 从 `stage_order = 1` 起**升序**累加；算第 1 级时「上方所有级质量」= 序号大于 1 的全部级 + 载荷 |

> **实现提示**：升序计算 + 降序渲染并不矛盾（计算遵循质量累加顺序，渲染要让玩家看到物理形状）。但**这是本项目最容易弄反的地方**，`05` 的详情页与 `06` 的 `vehicle_delta_v()` 都要写测试卡住。

**为什么用 `owner_type` + 双可空 FK，而不是别的**：
- ❌ 不用 `GenericForeignKey` —— 依赖 ContentType，**无法建立数据库级外键与 CHECK**，且 Admin 的 Generic 内联会绕过约束。
- ❌ 不用两张平行的 `CarrierStage`/`PayloadStage` 表 —— 两者结构完全一样，会产生双份表单/路由/校验。
- ✅ 火箭与载荷共用一张表，`owner_type` 判别归属。

### 4.9 `stages.StageTank` — 级-燃料罐挂载（需求⑥）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `stage` | FK(Stage) | **CASCADE**, related_name=`tanks` | 所属级 |
| `fuel_tank` | FK(FuelTank) | **PROTECT**, related_name=`stage_usages` | 燃料罐 |
| `quantity` | PositiveIntegerField | default=1 | 数量 |
| `mount_position` | CharField(10) | choices=`MountPosition`, default=`INLINE` | 安装方式 |
| `note` | CharField(100) | blank | 备注 |

```python
constraints = [
    UniqueConstraint(fields=["stage", "fuel_tank", "mount_position"], name="uniq_stage_tank_mount"),
    CheckConstraint(condition=Q(quantity__gte=1), name="stagetank_quantity_positive"),
]
```

> 一级挂 n 个燃料罐：**同型用 `quantity` 压缩**（4 个 FL-T800 = 一行 `quantity=4`），异型多行。

### 4.10 `sites.Site` — 发射场

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 发射场代号 |
| `name` | CharField(60) | unique | 发射场名称 |
| `body` | FK(Body) | **PROTECT**, related_name=`sites` | 所在天体 |
| `latitude` | FloatField | null, blank | 纬度 (°) |
| `longitude` | FloatField | null, blank | 经度 (°) |
| `altitude` | FloatField | default=0 | 海拔 (m) |
| `pad_level` | PositiveIntegerField | default=1 | 发射台等级 |
| `max_mass` | FloatField | null, blank | 最大起飞质量 (t) |
| `max_diameter` | FloatField | null, blank | 最大直径限制 (m) |
| `is_operational` | BooleanField | default=True | 可用 |
| `description` | TextField | blank | 说明 |
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

- `body` **必填**（KSP 发射场必然属于某天体；Mun/Minmus 基地也是发射场）
- **`clean()`**：`-90 <= latitude <= 90`、`-180 <= longitude <= 180`
- 经纬度用 **`FloatField`（十进制度数，西/南为负）**，**不要用字符串**——需要参与几何计算与范围查询。

### 4.11 `launches.FlightLog` — 发射日志（需求④的核心载体）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 任务编号（`SCP-` 前缀） |
| `name` | CharField(80) | — | 任务名称 |
| `state` | CharField(12) | choices=`FlightState`, default=`PLANNED`, db_index | 任务状态 |
| `planned_ut` | FloatField | null, blank | 计划发射时间 (UT) |
| `actual_ut` | FloatField | null, blank | 实际发射时间 (UT) |
| `carrier` | FK(CarrierModel) | **PROTECT**, related_name=`flights` | 运载火箭 |
| `payload` | FK(PayloadModel) | null, blank, **PROTECT**, related_name=`flights` | 有效载荷 |
| `site` | FK(Site) | **PROTECT**, related_name=`flights` | 发射场 |
| `crew_count` | PositiveIntegerField | default=0 | 乘员数 |
| `result_code` | IntegerField | null, blank | 结果编码 |
| `rest_dv` | IntegerField | null, blank | 剩余 Δv (m/s) |
| `cost` | PositiveIntegerField | default=0 | 任务成本 (√) |
| `detail` | TextField | blank | 任务详情 |
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

**`planned_ut` 与 `actual_ut` 分离，是「安排发射计划」这个核心诉求的落点** —— 待发任务是 `state=PLANNED` 且按 `planned_ut` 排序。

**`result_code` 语义（必须写进 `help_text`）**：

| 值 | 含义 |
|---|---|
| `NULL` | 尚未执行（`state=PLANNED`） |
| `-2` | 台架中止（T-0 前失败，发射夹未释放） |
| `-1` | 任务失败（各级工作正常，但设计缺陷导致任务失败） |
| `0` | 成功 |
| `>0` | **第 n 级失效**（值为失效的 `stage_order`） |

**约束与校验**：

```python
constraints = [
    CheckConstraint(condition=Q(result_code__isnull=True) | Q(result_code__gte=-2),
                    name="flight_result_code_range"),
    Index(fields=["state", "planned_ut"]),      # 「发射日程」视图的主查询
]
```

```python
def clean(self):
    # 状态-时间一致性：需要友好中文提示，所以放 clean() 而非 DB CHECK
    if self.state == FlightState.PLANNED and self.actual_ut is not None:
        raise ValidationError({"actual_ut": "计划中的任务不应有实际发射时间。"})
    if self.state in (FlightState.LAUNCHED, FlightState.FAILED) and self.actual_ut is None:
        raise ValidationError({"actual_ut": "已发射/失败的任务必须填写实际发射时间。"})
```

- `rest_dv` **可空**：`NULL` 表示未记录，`0` 表示真的没有剩余 Δv。两者语义不同，不要合并。
- `payload` 可空（有些任务无载荷，如纯测试飞行）；`carrier` 与 `site` 必填。

### 4.12 `programs.Program` — 航天计划（需求⑤的「1」端）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 计划代号 |
| `name` | CharField(80) | unique | 计划名称 |
| `objective` | TextField | — | 计划目标 |
| `status` | CharField(12) | choices=`ProgramStatus`, default=`PLANNED`, db_index | 计划状态 |
| `target_body` | FK(Body) | null, blank, **SET_NULL**, related_name=`programs` | 主要目标天体 |
| `start_ut` | FloatField | null, blank | 计划开始 (UT) |
| `end_ut` | FloatField | null, blank | 计划结束 (UT) |
| `budget` | PositiveIntegerField | null, blank | 预算 (√) |
| `spent` | PositiveIntegerField | default=0 | 已花费 (√) |
| `priority` | PositiveIntegerField | default=3 | 优先级（1 最高） |
| `description` | TextField | blank | 说明 |
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

- **约束**：`CheckConstraint(condition=Q(priority__gte=1) & Q(priority__lte=5), name="program_priority_range")`
- **`clean()`**：`end_ut >= start_ut`（都非空时）

### 4.13 `programs.ProgramLink` — 计划成员链接（需求⑤的「n」端）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `program` | FK(Program) | **CASCADE**, related_name=`links` | 所属计划 |
| `object_type` | CharField(12) | choices=`ProgramObjectType` | 成员类型 |
| `carrier` | FK(CarrierModel) | null, blank, **CASCADE**, related_name=`program_links` | 火箭 |
| `payload` | FK(PayloadModel) | null, blank, **CASCADE**, related_name=`program_links` | 载荷 |
| `flight` | FK(FlightLog) | null, blank, **CASCADE**, related_name=`program_links` | 发射日志 |
| `site` | FK(Site) | null, blank, **CASCADE**, related_name=`program_links` | 发射场 |
| `spacecraft` | FK(Spacecraft) | null, blank, **CASCADE**, related_name=`program_links` | 在轨航天器 |
| `role_note` | CharField(120) | blank | 在本计划中的角色 |
| `added_at` | DateTimeField | auto_now_add | 加入时间 |

**约束（照抄）**：

```python
class Meta:
    constraints = [
        CheckConstraint(
            condition=(
                Q(object_type="CARRIER",    carrier__isnull=False, payload__isnull=True,  flight__isnull=True, site__isnull=True, spacecraft__isnull=True)
                | Q(object_type="PAYLOAD",    carrier__isnull=True,  payload__isnull=False, flight__isnull=True, site__isnull=True, spacecraft__isnull=True)
                | Q(object_type="FLIGHT",     carrier__isnull=True,  payload__isnull=True,  flight__isnull=False, site__isnull=True, spacecraft__isnull=True)
                | Q(object_type="SITE",       carrier__isnull=True,  payload__isnull=True,  flight__isnull=True, site__isnull=False, spacecraft__isnull=True)
                | Q(object_type="SPACECRAFT", carrier__isnull=True,  payload__isnull=True,  flight__isnull=True, site__isnull=True, spacecraft__isnull=False)
            ),
            name="programlink_exactly_one_object",
        ),
        UniqueConstraint(fields=["program", "object_type", "carrier"],    name="uniq_program_carrier"),
        UniqueConstraint(fields=["program", "object_type", "payload"],    name="uniq_program_payload"),
        UniqueConstraint(fields=["program", "object_type", "flight"],     name="uniq_program_flight"),
        UniqueConstraint(fields=["program", "object_type", "site"],       name="uniq_program_site"),
        UniqueConstraint(fields=["program", "object_type", "spacecraft"], name="uniq_program_spacecraft"),
    ]
```

**基数（准确表述，不要写成 n:m）**：
- `Program (1) ── (n) ProgramLink`：一个计划可挂任意多个成员。
- **一个成员对象最多归属一个计划**（由那 5 条 `UniqueConstraint` 保证）。
- 5 条唯一约束能共存，是因为 **SQLite 里 `NULL` 不参与唯一性比较** —— 填了 `carrier` 的行其 `payload` 为 `NULL`，不会与其他行冲突。
- 若将来要允许「一个对象参与多个计划」，只需移除这 5 条唯一约束，**表结构不用改**。

### 4.14 `spacecraft.Spacecraft` — 在轨航天器（需求④）

| 字段 | 类型 | 约束 | 中文标签 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `code` | CharField(24) | unique, db_index | 航天器代号 |
| `name` | CharField(80) | unique | 航天器名称 |
| `source_flight` | FK(FlightLog) | null, blank, **SET_NULL**, related_name=`spacecraft` | 来源发射 |
| `source_carrier` | FK(CarrierModel) | null, blank, **SET_NULL**, related_name=`spacecraft` | 来源火箭 |
| `source_payload` | FK(PayloadModel) | null, blank, **SET_NULL**, related_name=`spacecraft` | 载荷 |
| `body` | FK(Body) | **PROTECT**, related_name=`spacecraft` | 当前所在天体 |
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
| `created_at` / `updated_at` | DateTimeField | auto | 创建/更新时间 |

**约束与校验**：

```python
constraints = [
    CheckConstraint(condition=Q(eccentricity__isnull=True) | Q(eccentricity__gte=0),
                    name="spacecraft_eccentricity_nonneg"),
    Index(fields=["body", "is_active", "situation"]),
]
```

```python
def clean(self):
    # e < 1 只对环绕轨道强制：逃逸轨道(situation=ESCAPING)天然是 e >= 1 的双曲线
    if self.eccentricity is not None:
        if self.situation in (Situation.ORBITING, Situation.DOCKED) and not (0 <= self.eccentricity < 1):
            raise ValidationError({"eccentricity": "环绕轨道的离心率必须在 0 到 1 之间。"})
        if self.eccentricity < 0:
            raise ValidationError({"eccentricity": "离心率不能为负。"})
    if self.inclination is not None and not (0 <= self.inclination <= 180):
        raise ValidationError({"inclination": "轨道倾角必须在 0 到 180 度之间。"})
    # 跨表规则：半长轴必须大于天体半径
    if self.sma is not None and self.body_id and self.sma <= self.body.radius:
        raise ValidationError({"sma": f"半长轴必须大于 {self.body.name} 的半径 {self.body.radius:.0f} m。"})
```

**⚠️ `sma` 不等于高度。** `sma` 是**轨道半长轴**（天体中心到轨道），高度 = `sma − Body.radius`。Kerbin 半径为 600 km，混淆两者会产生 600 km 量级的错误。录入表单必须给常驻提示（见 `docs/spec/04` §页面）。

**不落库的派生量**：`periapsis`、`apoapsis`、`period`、`orbital_speed` 一律**实时计算**（`services/orbital.py`），不建列 —— 独立存储必然与 `sma`/`eccentricity` 漂移。

**`cached_period_sec` 的作用**：玩家从 MechJeb/KER **抄录**的周期快照，仅作对照展示。界面上并列显示「计算值 / 录入值」，偏差 > 1% 时提示。这与 `CarrierModel.max_payload_mass`（声明值 vs 计算值）是同一套模式：**权威输入 + 可选抄录值**。

### 4.15 `on_delete` 策略总表

| 父 → 子 | 策略 |
|---|---|
| `CarrierModel` / `PayloadModel` → `Stage` | `CASCADE` |
| `Stage` → `StageTank` | `CASCADE` |
| `PartCatalog` → `FuelTank` / `Engine` / `ScienceInstrument` | `CASCADE` |
| `Engine` → `Stage.engine` | **`PROTECT`** |
| `FuelTank` → `StageTank.fuel_tank` | **`PROTECT`** |
| `Body` → `Site` / `Spacecraft` | **`PROTECT`** |
| `Body.parent` | **`PROTECT`** |
| `CarrierModel` / `PayloadModel` / `Site` → `FlightLog` | **`PROTECT`** |
| `FlightLog` / `CarrierModel` / `PayloadModel` → `Spacecraft.source_*` | `SET_NULL` |
| `Program` → `ProgramLink` | `CASCADE` |
| 任意对象 → `ProgramLink.*` | `CASCADE` |
| `Body` → `Program.target_body` | `SET_NULL` |
| `*.derived_from` | `SET_NULL` |

> **`PROTECT` 的地方必须在视图里捕获 `ProtectedError` 并转成友好提示**，否则用户删一个被引用的引擎会看到 500。见 `docs/spec/04` §错误处理。

---

## 5. 种子数据

### 5.1 `fixtures/bodies.json` — 17 个天体

**必做**。`Body.mu` 是轨道周期计算的输入，没有它周期算不出来。

| 天体 | `code` | `parent` | `radius` (m) | `mu` (m³/s²) | `soi_radius` (m) | `atmosphere_height` (m) | `sidereal_day` (s) | `surface_gravity` |
|---|---|---|---|---|---|---|---|---|
| Kerbol | `BODY-KERBOL` | — | 261 600 000 | 1.1723320×10¹⁸ | `null` | 0 | 432 000 | 17.13 |
| Kerbin | `BODY-KERBIN` | Kerbol | 600 000 | 3.531600×10¹² | 84 159 286 | 70 000 | 21 549.4 | 9.81 |
| Mun | `BODY-MUN` | Kerbin | 200 000 | 6.513839×10¹⁰ | 2 429 559 | 0 | 138 984 | 1.63 |
| Minmus | `BODY-MINMUS` | Kerbin | 60 000 | 1.765800×10⁹ | 2 247 428 | 0 | 40 400 | 0.491 |
| Duna | `BODY-DUNA` | Kerbol | 320 000 | 3.013632×10¹¹ | 47 921 949 | 50 000 | 65 517.86 | 2.94 |
| Ike | `BODY-IKE` | Duna | 130 000 | 1.856836×10¹⁰ | 1 049 599 | 0 | 65 517.86 | 1.10 |
| Eve | `BODY-EVE` | Kerbol | 700 000 | 8.171730×10¹² | 85 109 365 | 90 000 | 80 500 | 16.7 |
| Gilly | `BODY-GILLY` | Eve | 13 000 | 8.289455×10⁶ | 126 123 | 0 | 28 255 | 0.049 |
| Moho | `BODY-MOHO` | Kerbol | 250 000 | 1.686093×10¹¹ | 9 640 781 | 0 | 1 210 000 | 2.70 |
| Dres | `BODY-DRES` | Kerbol | 138 000 | 2.148448×10¹⁰ | 32 832 840 | 0 | 34 800 | 1.13 |
| Jool | `BODY-JOOL` | Kerbol | 6 000 000 | 2.825280×10¹⁴ | 2 455 985 042 | 200 000 | 36 000 | 7.85 |
| Laythe | `BODY-LAYTHE` | Jool | 500 000 | 1.962000×10¹² | 3 723 645 | 50 000 | 52 962 | 7.85 |
| Vall | `BODY-VALL` | Jool | 300 000 | 2.074815×10¹¹ | 2 406 401 | 0 | 105 962 | 2.31 |
| Tylo | `BODY-TYLO` | Jool | 600 000 | 2.825280×10¹² | 10 856 518 | 0 | 211 926 | 7.85 |
| Bop | `BODY-BOP` | Jool | 65 000 | 2.486834×10⁹ | 2 588 559 | 0 | 544 507 | 0.589 |
| Pol | `BODY-POL` | Jool | 44 000 | 7.217021×10⁸ | 2 042 599 | 0 | 901 903 | 0.373 |
| Eeloo | `BODY-EELOO` | Kerbol | 210 000 | 7.441083×10¹⁰ | 119 082 940 | 0 | 194 600 | 1.69 |

**其余字段的填法**：
- `is_star`：只有 Kerbol 为 `True`
- `is_reachable`：全部 `True`
- `has_atmosphere`：`atmosphere_height > 0` 的为 `True`（Kerbin/Mun 除外 → Mun 为 `False`；实际有大气的是 Kerbin、Duna、Eve、Jool、Laythe）
- `solar_day`：`sidereal_day × 21600 / 21549.4`（Kerbin 精确等于 21600）
- `sort_order`：按上表顺序 0–16

**JSON 片段示例**：

```json
[
  {
    "model": "core.body",
    "fields": {
      "code": "BODY-KERBIN", "name": "Kerbin", "name_en": "Kerbin",
      "parent": null, "radius": 600000.0, "mu": 3.5316e12,
      "soi_radius": 84159286.0, "atmosphere_height": 70000.0,
      "has_atmosphere": true, "sidereal_day": 21549.4, "solar_day": 21600.0,
      "surface_gravity": 9.81, "is_star": false, "is_reachable": true,
      "sort_order": 1, "description": "母星"
    }
  }
]
```

> **`parent` 要填主键 `id`**，所以 `fixtures` 里必须按「父天体在前」的顺序排列，或在 `loaddata` 后跑一次管理命令回填。建议用后者（`seed_bodies` 命令），更稳。
>
> **Kerbol 的 `soi_radius` 填 `null`**，不能写 `Infinity`（JSON 不支持）。

### 5.2 `fixtures/parts_sample.json` — KSP 原版部件样例

**必做，但只需 8–12 件样品**，让玩家看到数据形态即可，后续自行录入。

必须先建 `PartCatalog`，再建 1:1 子表（fixture 里用 `["part", "PART-FLT800"]` 之类的自然键，或分两个 fixture 文件按顺序加载）。

**建议的样品**（数值贴近 KSP 原版，可核对后微调）：

| 部件 | `part_type` | 直径 | 干重 (t) | 造价 | 专有字段 |
|---|---|---|---|---|---|
| FL-T800 燃料罐 | `TANK` | 1.25 | 0.5 | 800 | `wet_mass=4.5`, `capacity=800`, `fuel_type=LF_OX` |
| FL-T400 燃料罐 | `TANK` | 1.25 | 0.25 | 400 | `wet_mass=2.25`, `capacity=400`, `fuel_type=LF_OX` |
| FL-T200 燃料罐 | `TANK` | 1.25 | 0.125 | 200 | `wet_mass=1.125`, `capacity=200`, `fuel_type=LF_OX` |
| LV-909 "Terrier" | `ENGINE` | 1.25 | 0.5 | 390 | `thrust_asl=14.78`, `thrust_vac=60`, `isp_asl=85`, `isp_vac=345`, `cycle_type=EXPANDER`, `is_vacuum_optimized=True` |
| LV-T30 "Reliant" | `ENGINE` | 1.25 | 1.25 | 1100 | `thrust_asl=205.16`, `thrust_vac=240`, `isp_asl=265`, `isp_vac=310`, `cycle_type=GAS_GENERATOR` |
| RE-L10 "Poodle" | `ENGINE` | 2.5 | 1.75 | 1300 | `thrust_asl=64.29`, `thrust_vac=250`, `isp_asl=90`, `isp_vac=350`, `cycle_type=EXPANDER`, `is_vacuum_optimized=True`, `gimbal_range=5` |
| RT-10 "Hammer" 固推 | `ENGINE` | 1.25 | 0.75 | 400 | `thrust_asl=197.9`, `thrust_vac=227`, `isp_asl=170`, `isp_vac=195`, `cycle_type=SOLID`, `is_throttleable=False`, `ignitions=1` |
| Mystery Goo 实验 | `SCIENCE` | 1.25 | 0.05 | 800 | `experiment_type="神秘粘液观测"`, `data_value=13`, `is_repeatable=False`, `transmit_efficiency=30` |
| 材料研究台 | `SCIENCE` | 1.25 | 0.2 | 880 | `experiment_type="材料研究"`, `data_value=25`, `is_repeatable=False`, `transmit_efficiency=25` |
| 温度计 | `SCIENCE` | — | 0.005 | 900 | `experiment_type="温度扫描"`, `data_value=8`, `is_repeatable=True`, `transmit_efficiency=100`, `is_radial=True` |

> **固体助推（RT-10）建在 `Engine` 表**：它有推力和比冲，是引擎；其燃料是部件自带的（用 `capacity` 建模），所以**固推不需要单独的 `FuelTank` 行**。

加载顺序：

```powershell
python manage.py loaddata fixtures/bodies.json
python manage.py loaddata fixtures/parts_sample.json
```

---

## 6. migrations 顺序（有依赖，别乱）

`ProgramLink.spacecraft` 使 `programs` 依赖 `spacecraft`，而 `spacecraft` 又依赖 `launches`。正确的应用创建与迁移顺序：

```
core → parts → carriers → payloads → stages → sites → launches → spacecraft → programs
```

- `programs` 的 `0001_initial` **是最后一个**。
- 若 `makemigrations` 报循环依赖，说明 `INSTALLED_APPS` 顺序或 FK 引用写错了。
- `Stage` 同时引用 `carriers` 与 `payloads`，所以 `stages` 必须在两者之后。

**首次迁移是唯一的权威验证** —— 本文的模型代码已通过语法与内部一致性检查，但未在真实 Django 环境执行过（本机原本无 Django）。

---

## 7. 扩展说明

### 「族」表已被取消（不要再加回来）
曾设计 `EngineFamily`/`StageFamily`/`CarrierFamily`/`PayloadFamily` 四张「族」表，**已全部取消**，改用每张子表上的两列：

| 列 | 用途 |
|---|---|
| `series` | 分组/筛选（`AJ10`、`XLR86`、`Davy 2x`）。可空，不强制分类 |
| `derived_from` | 变体血缘自引用（`Davy 2B.derived_from = Davy 2`） |

「火箭族」概念没丢：`CarrierModel.objects.filter(series="Davy 2x")` 就是族视图，`GROUP BY series` 就是族统计。

### 一个对象参与多个计划
移除 `ProgramLink` 的 5 条 `UniqueConstraint` 即可，表结构不用改。

### 未来换 MySQL 8.4
Django ORM 层约 1 小时，但**数据需 `dumpdata`/`loaddata` 搬迁**，不是改连接串就行。CHECK 约束 MySQL 8 同样支持。

### SQLite 的已知限制（影响本设计的部分）
1. **CHECK 不支持子查询** → 跨表规则只能放 `clean()`（已在设计中体现）
2. **`NULL` 不参与 UNIQUE 比较** → `ProgramLink` 的 5 条唯一约束能共存（这是设计依赖的特性，换库时要确认）
3. **`VARCHAR(n)` 长度不强制** → 长度限制靠 Django 校验，别指望 DB
4. **递归 CTE 支持有限** → 天体树层级用 Python 遍历 `parent` 链，不用 SQL
