"""轨道与 Δv 计算（规格 §7 逐字实现）。

纯函数：只接受数字或模型实例，**不 import Django**，不做任何数据库查询。

三条铁律（规格 §7.1–§7.3）：
1. `m0` 必须包含本级干重 + 本级燃料 + **上方所有级 + 载荷**（本节用 reversed() 递推实现）。
2. Δv 用常数 `G0`，**不用所在天体的重力** —— 所以本文件里 delta v 相关函数的签名
   不出现任何 `g` / `gravity` / `body` 参数，物理上无法传错。
3. `sma` 是半长轴（天体中心到轨道），不是高度；高度 = `sma - Body.radius`。
"""

import math

from core.constants import G0, FUEL_UNIT_MASS, KERBIN_DAY


def orbital_period(sma, eccentricity, mu):
    """轨道周期。返回 (秒, Kerbin天数)；不可计算时返回 (None, None)。"""
    if sma is None or mu in (None, 0):
        return None, None
    if eccentricity is not None and eccentricity >= 1:
        return None, None          # 双曲线/抛物线轨道无周期
    if sma <= 0:
        return None, None
    seconds = 2 * math.pi * math.sqrt(sma ** 3 / mu)
    return seconds, seconds / KERBIN_DAY


def apsis(sma, eccentricity):
    """(近拱点半径, 远拱点半径)，米。sma 为空返回 (None, None)。"""
    if sma is None:
        return None, None
    e = eccentricity or 0.0
    return sma * (1 - e), sma * (1 + e)


def altitude(r, body_radius):
    """半径 → 相对天体表面的高度 (m)。"""
    if r is None or body_radius is None:
        return None
    return r - body_radius


def stage_dry_mass(stage):
    """一级的干重 (t) = 引擎干重×数量 + 燃料罐干重×数量 + 结构质量。"""
    m = stage.structure_mass or 0.0
    if stage.engine_id and stage.engine:
        m += (stage.engine.dry_mass or 0.0) * (stage.engine_count or 0)
    if stage.fuel_tank_id and stage.fuel_tank:
        m += (stage.fuel_tank.dry_mass or 0.0) * (stage.tank_count or 0)
    return m


def stage_fuel_mass(stage):
    """一级的燃料质量 (t) = 容量 × 数量 × FUEL_UNIT_MASS。"""
    if not (stage.fuel_tank_id and stage.fuel_tank):
        return 0.0
    return (stage.fuel_tank.capacity or 0.0) * (stage.tank_count or 0) * FUEL_UNIT_MASS


def stage_delta_v(stage, upper_mass):
    """单级 Δv (m/s)。

    upper_mass: 该级上方所有级的总质量 + 载荷质量 (t)。
    isp 选择：stage_order == 1 用 isp_asl，其余用 isp_vac。
    引擎/比冲缺失时返回 None。
    """
    if not (stage.engine_id and stage.engine):
        return None
    isp = stage.engine.isp_asl if stage.stage_order == 1 else stage.engine.isp_vac
    if not isp:
        return None
    fuel = stage_fuel_mass(stage)
    if fuel <= 0:
        return None
    dry = stage_dry_mass(stage)
    m0 = upper_mass + dry + fuel
    mf = upper_mass + dry
    if mf <= 0 or m0 <= mf:
        return None
    return isp * G0 * math.log(m0 / mf)


def vehicle_delta_v(rocket, payload_mass=0.0):
    """整枚火箭的逐级 Δv。

    返回 [{"stage_order", "m0", "mf", "fuel_mass", "delta_v", "cumulative"}, ...]
    按 stage_order **升序**排列。
    """
    stages = list(rocket.stages.order_by("stage_order"))
    upper = payload_mass or 0.0
    result = []
    for stage in reversed(stages):           # ★ 自最上级向下递推
        fuel = stage_fuel_mass(stage)
        dry = stage_dry_mass(stage)
        m0 = upper + dry + fuel
        dv = stage_delta_v(stage, upper)
        result.append({
            "stage_order": stage.stage_order,
            "m0": m0,
            "mf": upper + dry,
            "fuel_mass": fuel,
            "delta_v": dv,
            "cumulative": None,              # 下面填
        })
        upper = m0                           # ★ 本级点火质量成为下一级的 upper
    result.reverse()                         # 转回升序
    total = 0.0
    for row in result:
        if row["delta_v"] is not None:
            total += row["delta_v"]
            row["cumulative"] = total
    return result
