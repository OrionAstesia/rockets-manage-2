"""计算层单测（规格 §9）。

纯函数不碰数据库，所以用 SimpleTestCase 系（unittest.TestCase 即可）。
浮点一律用 assertAlmostEqual 或相对误差，**不要用 ==**。
"""

import inspect
import unittest
from datetime import date

from django.test import TestCase
from django.urls import reverse

from core.constants import FUEL_UNIT_MASS, G0, KERBIN_DAY
from core.models import Body
from fleet.models import Rocket, RocketStage
from ops.models import FlightLog, FlightState, GameMode, Save
from parts.models import Engine, FuelTank
from services.orbital import altitude, apsis, orbital_period, stage_delta_v
from spaceflight.models import CraftType, Site, Spacecraft

MU_KERBIN = 3.5316e12


class ConstantTests(unittest.TestCase):
    """§6：三个常量各有各的坑，写死在这里防止被"顺手改对"。"""

    def test_g0_is_standard_gravity(self):
        # 用所在天体的重力会得到错误的 Δv（§7.2），必须恒为 9.80665
        self.assertEqual(G0, 9.80665)

    def test_kerbin_day_is_sidereal(self):
        # 必须是恒星日 21549.4，不是太阳日 21600（§6）
        self.assertEqual(KERBIN_DAY, 21549.4)

    def test_fuel_unit_mass(self):
        self.assertEqual(FUEL_UNIT_MASS, 0.005)


class OrbitalPeriodTests(unittest.TestCase):
    """§9：周期。参考值 §7.4：Kerbin 100 km 圆轨 sma=700000 → 1958.13 s。"""

    def test_kerbin_100km_circular_orbit(self):
        seconds, days = orbital_period(700000.0, 0.0, MU_KERBIN)
        self.assertAlmostEqual(seconds, 1958.128, delta=0.01)
        # §9 写的是 0.09087（四舍五入值），这里按相对误差 1e-6 校验
        self.assertAlmostEqual(days, 0.0908670, delta=1e-6)
        self.assertLess(abs(days - 1958.128 / KERBIN_DAY) / days, 1e-6)

    def test_synchronous_orbit_is_one_kerbin_day(self):
        # §9：sma=3463331.361 → T = 21549.4 s = 1.0000 Kerbin 天
        seconds, days = orbital_period(3463331.361, 0.0, MU_KERBIN)
        self.assertAlmostEqual(seconds, 21549.4, delta=0.01)
        self.assertAlmostEqual(days, 1.0, delta=1e-6)

    def test_missing_inputs_return_none(self):
        self.assertEqual(orbital_period(None, 0.0, MU_KERBIN), (None, None))
        self.assertEqual(orbital_period(700000.0, 0.0, 0), (None, None))
        self.assertEqual(orbital_period(700000.0, 0.0, None), (None, None))

    def test_hyperbolic_orbit_has_no_period(self):
        # e >= 1 是双曲线/抛物线，没有周期
        self.assertEqual(orbital_period(700000.0, 1.2, MU_KERBIN), (None, None))
        self.assertEqual(orbital_period(700000.0, 1.0, MU_KERBIN), (None, None))

    def test_non_positive_sma_returns_none(self):
        self.assertEqual(orbital_period(0.0, 0.0, MU_KERBIN), (None, None))
        self.assertEqual(orbital_period(-1.0, 0.0, MU_KERBIN), (None, None))


class ApsisTests(unittest.TestCase):
    """§9：拱点。浮点误差真实存在（远拱点是 770000.0000000001），不能用 ==。"""

    def test_apsis_of_elliptical_orbit(self):
        periapsis, apoapsis = apsis(700000.0, 0.1)
        self.assertAlmostEqual(periapsis, 630000.0)
        self.assertAlmostEqual(apoapsis, 770000.0)

    def test_apsis_without_eccentricity_is_circular(self):
        self.assertEqual(apsis(700000.0, None), (700000.0, 700000.0))
        self.assertEqual(apsis(700000.0, 0.0), (700000.0, 700000.0))

    def test_apsis_without_sma(self):
        self.assertEqual(apsis(None, 0.1), (None, None))


class AltitudeTests(unittest.TestCase):
    """§7.3：sma 不是高度。Kerbin 半径 600 km ⇒ 100 km 圆轨 sma = 700000。"""

    def test_altitude_from_sma(self):
        self.assertEqual(altitude(700000.0, 600000.0), 100000.0)

    def test_altitude_with_missing_inputs(self):
        self.assertIsNone(altitude(None, 600000.0))
        self.assertIsNone(altitude(700000.0, None))


class DeltaVSignatureTests(unittest.TestCase):
    """§7.2 的防护：签名里不出现任何 g / gravity / body 参数，物理上无法传错。"""

    def test_stage_delta_v_has_no_gravity_parameter(self):
        params = list(inspect.signature(stage_delta_v).parameters)
        self.assertEqual(params, ["stage", "upper_mass"])


class HomePageTests(TestCase):
    """规格 §8.2：首页 = 近期发射 5 条（降序）+ 在役航天器按类型计数 + 存档列表。"""

    def setUp(self):
        self.save = Save.objects.create(
            name="生涯存档", game_mode=GameMode.CAREER, start_date=date(2026, 1, 1)
        )
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.engine = Engine.objects.create(name="引擎", dry_mass=0.5, isp_asl=85, isp_vac=345)
        self.tank = FuelTank.objects.create(name="燃料罐", dry_mass=0.5, capacity=800)
        self.rocket = Rocket.objects.create(name="火箭 A", program=self.save)
        RocketStage.objects.create(
            rocket=self.rocket, stage_order=1, engine=self.engine, fuel_tank=self.tank,
            engine_count=1, tank_count=1, structure_mass=0.2,
        )
        self.site = Site.objects.create(name="发射场", program=self.save, body=self.body)
        for day in range(1, 8):                       # 7 条，首页只该显示最近 5 条
            FlightLog.objects.create(
                name=f"任务 {day} 号", planned_date=date(2026, 10, day),
                rocket=self.rocket, site=self.site, program=self.save,
            )
        Spacecraft.objects.create(
            name="空间站 1", program=self.save, body=self.body,
            craft_type=CraftType.STATION, is_active=True,
        )
        Spacecraft.objects.create(
            name="空间站 2", program=self.save, body=self.body,
            craft_type=CraftType.STATION, is_active=True,
        )
        Spacecraft.objects.create(
            name="探测器 1", program=self.save, body=self.body,
            craft_type=CraftType.PROBE, is_active=True,
        )
        Spacecraft.objects.create(
            name="已退役探测车", program=self.save, body=self.body,
            craft_type=CraftType.ROVER, is_active=False,
        )

    def test_page_renders(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

    def test_only_five_most_recent_flights(self):
        response = self.client.get(reverse("core:home"))
        names = [f.name for f in response.context["recent_flights"]]
        self.assertEqual(names, ["任务 7 号", "任务 6 号", "任务 5 号", "任务 4 号", "任务 3 号"])
        self.assertContains(response, "任务 7 号")
        self.assertNotContains(response, "任务 2 号")

    def test_flight_without_planned_date_sinks_to_the_bottom(self):
        FlightLog.objects.create(
            name="日期未定任务", planned_date=None,
            rocket=self.rocket, site=self.site, program=self.save,
        )
        response = self.client.get(reverse("core:home"))
        names = [f.name for f in response.context["recent_flights"]]
        self.assertNotIn("日期未定任务", names)

    def test_active_spacecraft_counted_by_craft_type(self):
        response = self.client.get(reverse("core:home"))
        counts = response.context["spacecraft_counts"]
        self.assertEqual(counts["total"], 3)          # 退役的探测车不计入
        self.assertEqual(
            counts["rows"], [{"label": "空间站", "total": 2}, {"label": "探测器", "total": 1}]
        )
        self.assertContains(response, "空间站 2")
        self.assertContains(response, "探测器 1")
        self.assertNotContains(response, "探测车 1")

    def test_saves_are_listed(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "生涯存档")
        self.assertContains(response, "生涯模式")
        self.assertContains(response, "2026年1月1日")   # zh-hans 本地化日期

    def test_empty_state(self):
        FlightLog.objects.all().delete()
        Save.objects.all().delete()
        Spacecraft.objects.all().delete()
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "还没有任何发射记录或计划")
        self.assertContains(response, "没有在役航天器")
        self.assertContains(response, "还没有存档")

