"""计算层单测（规格 §9）。

纯函数不碰数据库，所以用 SimpleTestCase 系（unittest.TestCase 即可）。
浮点一律用 assertAlmostEqual 或相对误差，**不要用 ==**。
"""

import inspect
import unittest

from core.constants import FUEL_UNIT_MASS, G0, KERBIN_DAY
from services.orbital import altitude, apsis, orbital_period, stage_delta_v

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
