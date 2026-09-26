"""计算层单测（规格 §9）。

纯函数不碰数据库，所以用 SimpleTestCase 系（unittest.TestCase 即可）。
浮点一律用 assertAlmostEqual 或相对误差，**不要用 ==**。
"""

import inspect
import re
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


class SaveListPageTests(TestCase):
    """存档列表 `/saves/`：行内新建表单 + 存档表 + 在役航天器计数 + 近期发射 5 条。

    这些断言原来测的是 `/`（文档 11 第 2.1 节把存档列表搬到了 `/saves/`）。
    """

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
        response = self.client.get(reverse("core:save_list"))
        self.assertEqual(response.status_code, 200)

    def test_only_five_most_recent_flights(self):
        response = self.client.get(reverse("core:save_list"))
        names = [f.name for f in response.context["recent_flights"]]
        self.assertEqual(names, ["任务 7 号", "任务 6 号", "任务 5 号", "任务 4 号", "任务 3 号"])
        self.assertContains(response, "任务 7 号")
        self.assertNotContains(response, "任务 2 号")

    def test_flight_without_planned_date_sinks_to_the_bottom(self):
        FlightLog.objects.create(
            name="日期未定任务", planned_date=None,
            rocket=self.rocket, site=self.site, program=self.save,
        )
        response = self.client.get(reverse("core:save_list"))
        names = [f.name for f in response.context["recent_flights"]]
        self.assertNotIn("日期未定任务", names)

    def test_active_spacecraft_counted_by_craft_type(self):
        response = self.client.get(reverse("core:save_list"))
        counts = response.context["spacecraft_counts"]
        self.assertEqual(counts["total"], 3)          # 退役的探测车不计入
        self.assertEqual(
            counts["rows"], [{"label": "空间站", "total": 2}, {"label": "探测器", "total": 1}]
        )
        self.assertContains(response, "空间站 2")
        self.assertContains(response, "探测器 1")
        self.assertNotContains(response, "探测车 1")

    def test_saves_are_listed(self):
        response = self.client.get(reverse("core:save_list"))
        self.assertContains(response, "生涯存档")
        self.assertContains(response, "生涯模式")
        self.assertContains(response, "2026年1月1日")   # zh-hans 本地化日期

    def test_save_row_shows_counts_and_links_to_the_save(self):
        response = self.client.get(reverse("core:save_list"))
        self.assertContains(response, f"/saves/{self.save.pk}/")
        row = next(r for r in response.context["save_rows"] if r.pk == self.save.pk)
        self.assertEqual(row.rocket_total, 1)
        self.assertEqual(row.flight_total, 7)          # 两个 Count 都加了 distinct，不会被乘积放大

    def test_save_list_has_inline_create_form(self):
        response = self.client.get(reverse("core:save_list"))
        self.assertContains(response, 'action="/saves/new/"')

    def test_empty_state(self):
        FlightLog.objects.all().delete()
        Save.objects.all().delete()
        Spacecraft.objects.all().delete()
        response = self.client.get(reverse("core:save_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "还没有任何发射记录或计划")
        self.assertContains(response, "没有在役航天器")
        self.assertContains(response, "还没有存档")


class SaveCrudTests(TestCase):
    """文档 10 第 4.1 / 8.1：存档的增删改；删除确认页要列出连带数量。"""

    def setUp(self):
        self.save = Save.objects.create(name="生涯存档", game_mode=GameMode.CAREER)
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.rocket = Rocket.objects.create(name="火箭 A", program=self.save)
        self.site = Site.objects.create(name="发射场", program=self.save, body=self.body)

    def test_create_save(self):
        response = self.client.post(
            reverse("core:save_create"),
            {"name": "新存档", "start_date": "2026-02-02", "game_mode": GameMode.SANDBOX},
        )
        self.assertRedirects(response, reverse("core:save_list"))
        save = Save.objects.get(name="新存档")
        self.assertEqual(save.game_mode, GameMode.SANDBOX)
        self.assertEqual(save.start_date, date(2026, 2, 2))

    def test_update_save(self):
        response = self.client.post(
            reverse("core:save_update", args=[self.save.pk]),
            {"name": "改名了", "start_date": "", "game_mode": GameMode.SCIENCE},
        )
        self.assertRedirects(response, reverse("core:save_list"))
        self.save.refresh_from_db()
        self.assertEqual(self.save.name, "改名了")
        self.assertEqual(self.save.game_mode, GameMode.SCIENCE)

    def test_delete_confirm_page_lists_related_counts(self):
        FlightLog.objects.create(
            name="任务", rocket=self.rocket, site=self.site, program=self.save,
        )
        response = self.client.get(reverse("core:save_delete", args=[self.save.pk]))
        self.assertEqual(response.status_code, 200)
        for expected in ("火箭 1", "发射场 1", "发射日志 1", "航天器 0", "载荷 0"):
            self.assertContains(response, expected)

    def test_delete_without_confirmation_only_shows_page(self):
        """列表页行尾的删除表单不带 confirmed，只应跳到确认页而不是真删。"""
        response = self.client.post(reverse("core:save_delete", args=[self.save.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Save.objects.filter(pk=self.save.pk).exists())

    def test_confirmed_delete_cascades_to_contents(self):
        FlightLog.objects.create(
            name="任务", rocket=self.rocket, site=self.site, program=self.save,
        )
        response = self.client.post(
            reverse("core:save_delete", args=[self.save.pk]), {"confirmed": "yes"},
        )
        self.assertRedirects(response, reverse("core:save_list"))
        self.assertFalse(Save.objects.exists())
        self.assertFalse(Rocket.objects.exists())
        self.assertFalse(Site.objects.exists())
        self.assertFalse(FlightLog.objects.exists())

    def test_delete_blocked_by_foreign_flight_shows_message(self):
        """别的存档的日志引用了本存档的火箭 → 友好提示，不是 500。"""
        other = Save.objects.create(name="另一个存档")
        FlightLog.objects.create(
            name="跨存档任务", rocket=self.rocket, site=self.site, program=other,
        )
        response = self.client.post(
            reverse("core:save_delete", args=[self.save.pk]), {"confirmed": "yes"}, follow=True,
        )
        self.assertTrue(Save.objects.filter(pk=self.save.pk).exists())
        self.assertContains(response, "删除失败")


def nav_link(html, href):
    """取出指向 href 的那个 `<a>` 开标签，用来断言它有没有 `active` 类。

    直接对整页做 `assertNotContains(..., "active")` 会被别的活动元素误伤，
    所以按 href 精确定位（文档 11 §7.3）。
    """
    match = re.search(r'<a[^>]*href="%s"[^>]*>' % re.escape(href), html)
    return match.group(0) if match else ""


class SaveListHomeSplitTests(TestCase):
    """文档 11 第 7.2 节：`/` 是暂空主页，存档列表搬到 `/saves/`，侧栏三模块。"""

    MODULES = ("/saves/", "/reference/engines/", "/schedule/")

    def test_home_page_is_a_placeholder(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "主页建设中")
        self.assertNotContains(response, "近期发射")     # 统计与近期发射留在 /saves/
        self.assertNotContains(response, "还没有存档")

    def test_save_list_holds_the_archive_list(self):
        Save.objects.create(name="存档一")
        Save.objects.create(name="存档二")
        response = self.client.get(reverse("core:save_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "存档一")
        self.assertContains(response, "存档二")
        self.assertContains(response, "新建存档")
        self.assertContains(response, 'action="/saves/new/"')
        self.assertEqual(len(response.context["save_rows"]), 2)   # 与数据库里的存档数一致

    def test_sidebar_has_three_modules(self):
        content = self.client.get(reverse("core:home")).content.decode()
        for href in self.MODULES:
            with self.subTest(href=href):
                self.assertIn(f'href="{href}"', content)

    def test_sidebar_highlights_nothing_on_the_home_page(self):
        """主页不属于任何模块语义，所以侧栏三项都不高亮（文档 11 §3.1）。"""
        content = self.client.get(reverse("core:home")).content.decode()
        for href in self.MODULES:
            with self.subTest(href=href):
                self.assertNotIn("active", nav_link(content, href))

    def test_sidebar_highlights_the_current_module(self):
        for url, href in (
            (reverse("core:save_list"), "/saves/"),
            (reverse("parts:engine_list"), "/reference/engines/"),
            (reverse("ops:schedule"), "/schedule/"),
        ):
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                self.assertIn("active", nav_link(content, href))



