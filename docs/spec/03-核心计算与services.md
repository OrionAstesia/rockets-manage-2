# 核心计算与 services 层

> 实现 `services/orbital.py`、`services/deltav.py`、`services/stats.py` 时照本文写。
> 这些是**纯函数**：不 import Django 视图、不碰 request，只接受数据、返回数据 —— 因此可以直接用数值断言测试。

KSP 用简化的二体问题与球形天体。本文的公式在 KSP 的物理模型下成立。

---

## 1. 常数与两个不同的「g」（最容易搞错）

```python
# core/constants.py
G0 = 9.80665            # 标准重力加速度 (m/s²)
FUEL_UNIT_MASS = 0.005  # t/单位（1 单位 = 5 kg）
KERBIN_DAY = 21600.0    # KSP 太阳日 (s)，仅展示层换算「天」
```

### ⚠️ Δv 用 `G0`（绝对常数），TWR 用当地重力 —— 两个公式用两个不同的 g

| 量 | 用什么重力 | 为什么 |
|---|---|---|
| **Δv**（火箭方程） | `G0 = 9.80665`，**绝对常数** | 比冲的单位定义是 $I_{sp} \equiv F/(\dot m\,g_0)$，$g_0$ 是**定义这个单位时约定的常数**，不是环境属性 |
| **TWR**（推重比） | $g_{local} = \mu/r^2$，**当地值** | TWR 是推力与当地重力的比值，是真实的力比较 |

**这个错误是无声的，所以必须防**：

| 使用的地 g | `isp=345, m0/mf=2.5` 的结果 | 偏差 |
|---|---|---|
| ✅ `G0 = 9.80665` | **3100.08 m/s** | 基准 |
| ❌ Kerbin 表面 `9.81` | 3101.14 m/s | +0.03%（**在母星上测试永远发现不了**） |
| ❌ Mun 表面 `1.63` | 515.28 m/s | **−83.4%（灾难性）** |
| ❌ Minmus 表面 `0.491` | 155.22 m/s | −95.0% |

**防护措施**：`services/deltav.py` 里 `G0` 只从 `core/constants.py` 导入，**函数签名中不出现任何 `g` / `gravity` / `body` 参数**（物理上无法传错）；并加一条负例断言 `Δv != isp * g_mun * ln(m0/mf)`。

---

## 2. Δv：齐奥尔科夫斯基公式

$$\Delta v = I_{sp} \cdot g_0 \cdot \ln\frac{m_0}{m_f}$$

| 符号 | 含义 | 单位 | 来源 |
|---|---|---|---|
| $I_{sp}$ | 比冲 | s | `Engine.isp_asl` 或 `Engine.isp_vac`（见 §2.3） |
| $g_0$ | **常数 9.80665** | m/s² | `core/constants.G0` |
| $m_0$ | 该级**点火时**的全部质量 | t | 见 §2.2 |
| $m_f$ | 该级**燃尽时**质量 = $m_0 - m_{fuel}$ | t | 见 §2.2 |

### 2.1 单级的干重与燃料质量

$$m_{dry} = \sum_{k \in StageTank}\big(m_{dry,part}^{(k)} \times q_k\big) + m_{dry,engine} \times n_{engine} + m_{decoupler}$$

$$m_{fuel} = \sum_{k \in StageTank}\big(capacity_k \times q_k\big) \times \texttt{FUEL\_UNIT\_MASS}$$

| 符号 | 来源 |
|---|---|
| $m_{dry,part}^{(k)}$ | `StageTank.fuel_tank.part.dry_mass` |
| $q_k$ | `StageTank.quantity` |
| $m_{dry,engine}$ | `Stage.engine.part.dry_mass` |
| $n_{engine}$ | `Stage.engine_count` |
| $m_{decoupler}$ | `Stage.decoupler_mass` |
| $capacity_k$ | `FuelTank.capacity` |

> **`FuelTank.wet_mass` 不参与 Δv 计算** —— 它是展示用字段（玩家从游戏抄的满载质量）。计算只用 `part.dry_mass` 与 `capacity`。理由：保持单一权威输入；同时用两者会导致玩家改一个忘改另一个就自相矛盾。

### 2.2 ⚠️ `m₀` 必须包含上方所有级 + 载荷（最容易算错的地方）

火箭是叠罗汉：最下面一级点火时，必须把它**上面的一切**都推上去。

**❌ 错误**：$m_0 = m_{dry}^{(本级)} + m_{fuel}^{(本级)}$（只算本级）

**✅ 正确**：
$$m_0^{(本级)} = m_{dry}^{(本级)} + m_{fuel}^{(本级)} + \sum_{j\ \text{上方各级}}\big(m_{dry}^{(j)} + m_{fuel}^{(j)}\big) + m_{payload}$$

**实现用这个递推形式**（自最上级向最下级遍历）：

```python
upper = payload_mass                      # 从最顶端开始
for stage in reversed(stages):            # stages 按 stage_order 升序，reversed = 自最上级开始
    m0 = upper + dry(stage) + fuel(stage)
    mf = upper + dry(stage)
    dv[stage] = isp * G0 * math.log(m0 / mf)
    upper = m0                            # ★ 本级点火质量成为下一级的 upper
```

**质量闭合恒等式**（写进单测，是发现「漏算某一级」的最有效手段）：

$$m_0^{(1)} = \sum_{\text{全部级}}\big(m_{dry} + m_{fuel}\big) + m_{payload} = \text{总起飞质量}$$

**三级例子**（`stage_order=1` 在最下面）：

```text
                    ▲
                    │  ┌───────────────────────────┐
                    │  │  PayloadModel.mass  1.500 t│
                    │  ├───────────────────────────┤
                    │  │  Stage 3  dry 0.625 t      │  ← 这 4.125 t
     Stage 3 的 m0  │  │           fuel 2.000 t     │     要被 S2 推
                    │  └───────────────────────────┘
                    │  ┌───────────────────────────┐
                    │  │  Stage 2  dry 1.550 t      │  ← 这 13.675 t
     Stage 2 的 m0  │  │           fuel 8.000 t     │     要被 S1 推
                    │  └───────────────────────────┘
                    │  ┌───────────────────────────┐
                    │  │  Stage 1  dry 4.800 t      │  ← 这 36.475 t
     Stage 1 的 m0  │  │           fuel 18.000 t    │     压在发射台上
                    │  └───────────────────────────┘
                    ▼
                 发射台 / Site
```

- `m0(S3) = 1.5 + 0.625 + 2.0 = 4.125 t`
- `m0(S2) = 4.125 + 1.55 + 8.0 = 13.675 t`
- `m0(S1) = 13.675 + 4.8 + 18.0 = 36.475 t` ← 即总起飞质量
- 闭合校验：`4.8 + 1.55 + 0.625 + 18.0 + 8.0 + 2.0 + 1.5 = 36.475` ✅

### 2.3 比冲的选择

| 阶段 | 用哪个字段 |
|---|---|
| 大气段（起飞级） | `Engine.isp_asl` |
| 真空段（其余各级） | `Engine.isp_vac` |

**v1 简化规则**：`stage_order == 1` 用 `isp_asl`，其余用 `isp_vac`；`use_vacuum_isp` 参数允许调用方覆盖。

### 2.4 燃料质量分数（判断级设计是否合理）

$$\zeta = \frac{m_{fuel}}{m_0} = 1 - \frac{1}{R}, \qquad R = \frac{m_0}{m_f}$$

KSP 化学推进级的典型 $\zeta \approx 0.75\text{–}0.85$。若 $\zeta < 0.5$，说明干重占比过大，Δv 会明显偏低 —— 可在详情页给出提示。

---

## 3. 推重比（TWR）

$$\text{TWR} = \frac{F}{m_0 \cdot g_{local}}, \qquad g_{local} = \frac{\mu}{r^2}$$

- $F$ = `Engine.thrust_asl`（起飞判定）× `engine_count`；真空判定用 `thrust_vac`
- **起飞判定取 $r = \texttt{Body.radius}$**（不是"高度 0"之外的东西；`sma` 与高度无关，这里用的是半径）

**验算**：Kerbin $g_{local}(R) = 3.5316\times10^{12} / 600000^2 = 9.8100$ m/s²，与 `Body.surface_gravity = 9.81` 一致 ✅

### 判定阈值（详情页按此着色）

| TWR | 判定 | 提示 |
|---|---|---|
| `< 1.0` | ❌ 飞不起来 | 「推重比不足 1，无法离地」 |
| `1.0 – 1.2` | ⚠️ 勉强 | 「推重比偏低，起飞加速缓慢」 |
| `1.2 – 1.7` | ✅ **合理区间** | 「推重比合理」 |
| `1.7 – 2.5` | ✅ 可用 | — |
| `> 2.5` | ⚠️ 过推 | 「推重比过高，气动损失大」 |

> **上面级 TWR < 1 不算错误**：真空中没有重力损失，上面级可以 TWR < 1 缓慢加速。阈值只对**起飞级**（`stage_order == 1`）判定。

---

## 4. 轨道计算

### 4.1 轨道周期（需求④「周期信息」的落点）

$$T = 2\pi\sqrt{\frac{a^3}{\mu}}$$

- $a$ = `Spacecraft.sma`（半长轴），$\mu$ = `Body.mu`
- **`e >= 1`（逃逸/双曲线）时 $T$ 无意义 → 返回 `None`**，界面显示「双曲线轨迹，无周期」而非报错

> **周期是派生量，不落库。** 理由是 $T$ 是 $a$ 与 $\mu$ 的函数，独立存储必然漂移。
> `Spacecraft.cached_period_sec` 是玩家从 MechJeb/KER **抄录**的快照，仅用于「计算值 vs 录入值」对照展示，偏差 > 1% 时提示。**不要把它当权威输入。**

### 4.2 ⚠️ `sma` 不是高度

| 量 | 定义 | 关系 |
|---|---|---|
| `sma`（半长轴 $a$） | 天体**中心**到轨道的距离 | 权威输入 |
| 高度 altitude | 距天体**表面** | $= a - \texttt{Body.radius}$（近圆轨道） |

Kerbin 半径 600 km，混淆两者 = 600 km 量级误差。录入表单常驻提示，`Spacecraft.clean()` 校验 `sma > body.radius`。

### 4.3 近拱点 / 远拱点 / 轨道速度

$$r_p = a(1-e), \qquad r_a = a(1+e)$$

$$v = \sqrt{\mu\left(\frac{2}{r} - \frac{1}{a}\right)} \quad\text{(vis-viva)}$$

**展示用高度而非半径**（玩家习惯）：拱点高度 $= r_{p,a} - \texttt{Body.radius}$。

### 4.4 同步轨道半长轴

$$a_{sync} = \left(\mu\left(\frac{T_{sidereal}}{2\pi}\right)^2\right)^{1/3}$$

**⚠️ 必须用恒星日（`Body.sidereal_day`），不是太阳日。**

| 天体 | `mu` | `sidereal_day` | $a_{sync}$ (m) | 同步高度 (km) |
|---|---|---|---|---|
| Kerbin | 3.5316e12 | 21549.4 | 3 463 331 | 2 863.33 |
| Mun | 6.513839e10 | 138984.0 | 3 170 557 | 2 970.56 |
| Minmus | 1.7658e9 | 40400.0 | 417 941 | 357.94 |
| Duna | 3.013632e11 | 65517.86 | 3 200 000 | 2 880.00 |
| Dres | 2.148448e10 | 34800.0 | 870 244 | 732.24 |
| Jool | 2.825280e14 | 36000.0 | 21 010 461 | 15 010.46 |
| Moho | 1.686093e11 | 1210000.0 | 18 423 162 | 18 173.16 |

**KSP 社区常引用的「Kerbin 同步轨道高度 2 868.75 km」对应的是太阳日 21 600 s**，而用恒星日 21 549.4 s 算得 2 863.33 km。`Body` 同时保留两列正是为消除这种混淆 —— **周期公式一律用恒星日**。

### 4.5 霍曼转移（v1 只做计算展示，不做规划器）

$$\Delta v_1 = \sqrt{\frac{\mu}{r_1}}\left(\sqrt{\frac{2r_2}{r_1+r_2}} - 1\right), \qquad \Delta v_2 = \sqrt{\frac{\mu}{r_2}}\left(1 - \sqrt{\frac{2r_1}{r_1+r_2}}\right)$$

转移时间 = 半个转移椭圆周期 $= \frac{1}{2}\cdot 2\pi\sqrt{a_t^3/\mu}$，其中 $a_t = (r_1+r_2)/2$。

**验算**：Kerbin 100 km LKO → Mun 轨道（$r_1 = 700000$，$r_2 = 12000000$，$\mu = 3.5316\times10^{12}$）：$\Delta v_1 = 841.6$、$\Delta v_2 = 362.4$、合计 $1204.0$ m/s，转移时间 $26750$ s（1.24 天）。

---

## 5. 已知简化与误差方向（必须在界面上如实标注）

**系统算出的 Δv 是理想上界，实际入轨所需比它高。** 这是给玩家的关键提示。

| # | 简化 | 影响方向 | 量级 |
|---|---|---|---|
| E-1 | 忽略气动损失（阻力、重力转向损失） | 计算值**偏乐观** | 实际入轨 Δv 比理论高约 10–20% |
| E-2 | 忽略发动机启动/关机瞬态与推力爬升 | 偏乐观 | 小 |
| E-3 | 忽略燃料残余与不可用燃料 | 偏乐观 | 小 |
| E-4 | 比冲按「大气段/真空段」两段近似（真实是连续变化） | 双向 | 小 |
| E-5 | `FUEL_UNIT_MASS = 0.005` 为 LF/OX 混合平均（不分账） | 双向 | 量级正确；与原版燃料罐容量精确吻合（见 `02` §2） |
| E-6 | 假设**级严格按 `stage_order` 顺序点燃、燃尽即抛** | 双向 | **若开启燃料交叉供给（`allow_fuel_crossfeed`），此模型失效、结果会错** |
| E-7 | 二体问题、球形天体、无摄动（KSP 原版本就如此） | — | 与游戏一致，不算简化 |

**E-6 要特别留意**：`PartCatalog.allow_fuel_crossfeed` 为真的部件，一个引擎可以消耗**其他级**燃料罐的燃料，会改变各级的 $m_0/m_f$。v1 **不做**交叉供给感知的计算，只在部件详情页给出静态提示。

---

## 6. services 接口（照这些签名实现）

### 6.1 `services/orbital.py`

```python
def orbital_period(sma: float | None, mu: float | None) -> float | None:
    """轨道周期 (s)。sma/mu 为空时返回 None。"""

def apsis(sma: float | None, eccentricity: float | None) -> tuple[float, float] | None:
    """(近拱点半径, 远拱点半径)，单位 m。"""

def orbital_velocity(r: float | None, sma: float | None, mu: float | None) -> float | None:
    """vis-viva 给出的该处轨道速度 (m/s)。"""

def synchronous_sma(sidereal_day: float | None, mu: float | None) -> float | None:
    """同步轨道半长轴 (m)。传入的是恒星日。"""

def altitude_from_radius(r: float | None, body_radius: float | None) -> float | None:
    """半径 → 相对天体表面的高度 (m)。"""

def spacecraft_orbit_summary(spacecraft) -> dict:
    """汇总一个 Spacecraft 的轨道派生量，供详情页与 AJAX 复用。"""
```

**边界情况（必须处理，不许抛异常）**：

| 输入 | 返回 |
|---|---|
| `sma is None` 或 `mu is None` 或 `mu == 0` | `None` |
| `eccentricity >= 1`（双曲线） | 周期 `None`；`apsis` 返回 `(rp, None)` |
| `sma <= body_radius` | 由 `clean()` 拦截，服务层仍应容忍 |
| 数字字符串（`"700000"`） | **接受**（`float()` 转换）—— Django `cleaned_data` 与 CSV 导入会给字符串，这是有意设计 |

### 6.2 `services/deltav.py`

```python
class StageDeltaV:                  # 数据类：stage / m0 / mf / fuel_mass / isp / delta_v / cumulative
    ...

def stage_dry_mass(stage) -> float:                     # 本级干重 (t)
def stage_fuel_mass(stage) -> float:                    # 本级燃料质量 (t)

def stage_delta_v(stage, upper_mass: float, use_vacuum_isp: bool) -> tuple[float | None, dict]:
    """单级 Δv。返回 (dv, 中间量字典) 便于页面展示推导过程。"""

def vehicle_delta_v(carrier=None, payload=None) -> list[StageDeltaV]:
    """★ 逐级 Δv，按 stage_order 升序，含累计值。payload 参与则计入 m0。"""

def liftoff_twr(carrier, payload, body) -> float | None:
    """起飞推重比。用 Body.mu / Body.radius**2 作当地重力。"""

def twr_verdict(twr: float | None) -> tuple[str, str]:
    """→ (级别, 中文提示)，用于页面着色与文案。级别取自 §3 的阈值表。"""
```

**`vehicle_delta_v` 的实现要点**：
- 只取 `owner_type='CARRIER'` 的级（载荷的级单独算）；若传了 `payload`，把 `payload.mass` 作为最顶端的 `upper` 起始值
- **按 `stage_order` 升序排序后 `reversed()` 遍历**（自最上级开始递推，见 §2.2）
- `engine` 为空的级：`dv` 返回 `None` 并跳过，不中断整枚火箭的计算

### 6.3 `services/stats.py`

```python
class ProgramProgress:              # 数据类：各状态计数、预算执行率、成员数

def program_progress(program) -> ProgramProgress:
    """计划的进度汇总（供计划总览页）。"""

def launch_success_rate(queryset) -> float | None:
    """发射成功率。以 result_code == 0 计成功；无已执行任务时返回 None。"""

def body_activity(body) -> dict:
    """该天体下的发射场数、航天器数、按状态分组的航天器计数。"""

def launch_stats_by_year(queryset) -> list[dict]:
    """按 KSP 年统计发射数（用 KERBIN_DAY 换算年份）。"""
```

---

## 7. 单元测试（必需，P0 就要建起来）

`services/` 三个模块都必须有测试，用 `manage.py test`。测试文件：`services/tests/test_orbital.py`、`test_deltav.py`、`test_stats.py`。

### 7.1 断言值（已实测，直接用）

| 用例 | 输入 | 期望 |
|---|---|---|
| **同步轨道自洽性**（推荐主用例） | 对每个天体：`orbital_period(synchronous_sma(b.sidereal_day, b.mu), b.mu)` | `≈ b.sidereal_day`，相对误差 < 1e-9 |
| Kerbin 同步轨道 | `mu=3.5316e12`, `sidereal_day=21549.4` | `a_sync ≈ 3463331.361` m（高度 2863.33 km） |
| 单级 Δv | `isp=345`, `m0=10`, `mf=4` | `3100.081 m/s` |
| 起飞 TWR | `thrust=200 kN × 4`, `m0=40 t`, `g=9.81` | `2.0387` |
| 近远拱点 | `sma=700000`, `e=0.1` | `(630000.0, 770000.0)` |
| Kerbin 100 km 低轨周期 | `sma=700000`, `mu=3.5316e12` | `1958.128 s` |
| Kerbin 70 km 周期 | `sma=670000` | `1833.607 s` |
| 三级手算例题 | 见 `archive/06` §4 的完整配置 | 总 Δv `6887.36 m/s`；起飞质量 `36.475 t`；起飞 TWR `1.2297` |
| 霍曼 Kerbin LKO→Mun | `r1=700000`, `r2=12000000` | `Δv1=841.6`, `Δv2=362.4`, 合计 `1204.0 m/s`；转移时间 `26750 s` |

> ⚠️ **`sma` 用量的警示**：`sma = 700000` 是**高度 100 km** 的轨道（因为要加 Kerbin 半径 600 km）。`1837 s` 不是这个轨道的周期 —— 它对应 `sma = 670000`（高度 70 km）。设计阶段在这里错过两次，**写测试时务必显式写明是 `sma` 还是高度**。

### 7.2 必测的边界与负例

```python
# 1) 空值不抛异常
assert orbital_period(None, 3.5316e12) is None
assert orbital_period(700000, None) is None
assert orbital_period(700000, 0) is None

# 2) 双曲线轨道无周期
assert orbital_period(700000, 3.5316e12, eccentricity=1.2) is None   # 若签名支持
# 或在 apsis() 层面：e >= 1 时远拱点为 None

# 3) ★ 负例：Δv 不得使用当地重力（防"无声 bug"回归）
g_mun = 6.513839e10 / 200000**2
assert abs(delta_v - 345 * g_mun * math.log(2.5)) > 1.0

# 4) ★ 质量闭合恒等式（发现漏算某一级）
assert m0_of_stage_1 == pytest.approx(total_dry + total_fuel + payload_mass)

# 5) 浮点比较用 assertAlmostEqual，不要用 ==
#    apsis(700000, 0.1)[1] 实际返回 770000.0000000001
```

### 7.3 数位与容差约定

- 浮点比较一律用 `assertAlmostEqual` 或 `pytest.approx`，**不要用 `==`**
- 周期/Δv 用相对误差：`< 1e-9`（同步轨道自洽性）、`< 0.01`（对比社区参考值）
- 长度量容差 `1 m` 足够（KSP 精度不需要更高）
