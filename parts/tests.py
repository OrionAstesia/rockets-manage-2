"""部件库冒烟测试 + 参考数据四个列表页（文档 11 第 4.3 / 7.1 / 7.2 节）。"""

import re

from django.test import TestCase
from django.urls import reverse

from core.models import Body
from fleet.models import Rocket, RocketStage
from ops.models import Save

from .models import Engine, FuelTank, FuelType, ScienceInstrument


def subnav_link(html, href):
    """取出指向 href 的 `<a>` 开标签（用来断言 active，不看别的活动元素）。"""
    match = re.search(r'<a[^>]*href="%s"[^>]*>' % re.escape(href), html)
    return match.group(0) if match else ""


class PartsModelTests(TestCase):
    def test_create_fuel_tank(self):
        tank = FuelTank.objects.create(
            name="FL-T800", diameter=1.25, dry_mass=0.5, capacity=800,
            fuel_type=FuelType.LF_OX, cost=800,
        )
        self.assertEqual(str(tank), "FL-T800")
        self.assertEqual(FuelTank.objects.get(pk=tank.pk).capacity, 800)

    def test_fuel_tank_defaults(self):
        tank = FuelTank.objects.create(name="默认罐")
        self.assertEqual(tank.fuel_type, FuelType.LF_OX)
        self.assertEqual(tank.dry_mass, 0)
        self.assertEqual(tank.capacity, 0)
        self.assertEqual(tank.cost, 0)

    def test_create_engine(self):
        engine = Engine.objects.create(
            name="LV-T45", diameter=1.25, dry_mass=1.5, thrust_asl=167.97,
            thrust_vac=215.0, isp_asl=85, isp_vac=165, cost=1200,
        )
        self.assertEqual(str(engine), "LV-T45")
        self.assertEqual(engine.isp_vac, 165)

    def test_create_science_instrument(self):
        instrument = ScienceInstrument.objects.create(
            name="温度计", dry_mass=0.005, experiment_type="温度",
            data_value=8, is_repeatable=True, requires_crew=False, cost=900,
        )
        self.assertEqual(str(instrument), "温度计")
        self.assertFalse(ScienceInstrument.objects.get(pk=instrument.pk).requires_crew)

    def test_name_is_unique(self):
        FuelTank.objects.create(name="重复名")
        with self.assertRaises(Exception):
            FuelTank.objects.create(name="重复名")

    def test_ordering_by_name(self):
        FuelTank.objects.create(name="B 罐")
        FuelTank.objects.create(name="A 罐")
        self.assertEqual([t.name for t in FuelTank.objects.all()], ["A 罐", "B 罐"])


class ReferenceListPagesTests(TestCase):
    """文档 11 第 4.3 / 7.1 节：参考数据拆成四页，各自计数、各自只读规则。"""

    def setUp(self):
        Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000, has_atmosphere=True)
        Engine.objects.create(name="引擎 A", diameter=1.25, dry_mass=1.5, isp_asl=85, isp_vac=345)
        Engine.objects.create(name="引擎 B")
        FuelTank.objects.create(name="燃料罐 A", capacity=800)
        ScienceInstrument.objects.create(name="温度计", dry_mass=0.005, data_value=8)

    def test_four_pages_render_with_their_own_count(self):
        expectations = {
            "parts:engine_list": "共 2 个引擎",
            "parts:fueltank_list": "共 1 个燃料罐",
            "parts:instrument_list": "共 1 个科学设备",
            "parts:body_list": "共 1 个天体",
        }
        for name, text in expectations.items():
            with self.subTest(url_name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_each_page_has_exactly_one_table(self):
        """拆页回归：一页只显示一张表。"""
        for name in (
            "parts:engine_list", "parts:fueltank_list",
            "parts:instrument_list", "parts:body_list",
        ):
            with self.subTest(url_name=name):
                content = self.client.get(reverse(name)).content.decode()
                self.assertEqual(content.count("<table"), 1)

    def test_bodies_page_is_read_only(self):
        response = self.client.get(reverse("parts:body_list"))
        self.assertContains(response, "Kerbin")
        self.assertNotContains(response, "+ 新增")
        self.assertNotContains(response, ">操作<")
        self.assertNotContains(response, "bodies/new")     # 天体没有任何 CRUD 路由

    def test_old_reference_url_redirects_to_engines(self):
        response = self.client.get(reverse("parts:reference"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("parts:engine_list"))

    def test_engine_crud_from_dialogs(self):
        url = reverse("parts:engine_list")
        response = self.client.post(
            url,
            {
                "action": "create", "prefix": "new",
                "new-name": "新引擎", "new-diameter": "2.5", "new-dry_mass": "3",
                "new-thrust_asl": "200", "new-thrust_vac": "240", "new-isp_asl": "90",
                "new-isp_vac": "350", "new-cost": "1500",
            },
        )
        self.assertRedirects(response, url)
        engine = Engine.objects.get(name="新引擎")
        self.assertEqual(engine.isp_vac, 350)

        response = self.client.post(
            url,
            {
                "action": "update", "pk": engine.pk, "prefix": f"e{engine.pk}",
                f"e{engine.pk}-name": "改过的引擎", f"e{engine.pk}-diameter": "2.5",
                f"e{engine.pk}-dry_mass": "3", f"e{engine.pk}-thrust_asl": "200",
                f"e{engine.pk}-thrust_vac": "240", f"e{engine.pk}-isp_asl": "90",
                f"e{engine.pk}-isp_vac": "355", f"e{engine.pk}-cost": "1500",
            },
        )
        self.assertRedirects(response, url)
        engine.refresh_from_db()
        self.assertEqual(engine.name, "改过的引擎")
        self.assertEqual(engine.isp_vac, 355)

        response = self.client.post(
            url, {"action": "delete", "pk": engine.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, url)
        self.assertFalse(Engine.objects.filter(pk=engine.pk).exists())

    def test_fueltank_and_instrument_crud_from_dialogs(self):
        tanks_url = reverse("parts:fueltank_list")
        response = self.client.post(
            tanks_url,
            {"action": "create", "prefix": "new",
             "new-name": "新罐", "new-diameter": "1.25", "new-dry_mass": "0.25",
             "new-capacity": "400", "new-fuel_type": "XENON", "new-cost": "300"},
        )
        self.assertRedirects(response, tanks_url)
        self.assertEqual(FuelTank.objects.get(name="新罐").fuel_type, FuelType.XENON)

        instruments_url = reverse("parts:instrument_list")
        response = self.client.post(
            instruments_url,
            {"action": "create", "prefix": "new",
             "new-name": "新设备", "new-dry_mass": "0.02", "new-experiment_type": "重力",
             "new-data_value": "12", "new-is_repeatable": "on", "new-requires_crew": "",
             "new-cost": "500"},
        )
        self.assertRedirects(response, instruments_url)
        instrument = ScienceInstrument.objects.get(name="新设备")
        self.assertTrue(instrument.is_repeatable)
        self.assertFalse(instrument.requires_crew)

        response = self.client.post(
            tanks_url,
            {"action": "delete", "pk": FuelTank.objects.get(name="新罐").pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, tanks_url)
        response = self.client.post(
            instruments_url, {"action": "delete", "pk": instrument.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, instruments_url)
        self.assertFalse(FuelTank.objects.filter(name="新罐").exists())
        self.assertFalse(ScienceInstrument.objects.filter(pk=instrument.pk).exists())

    def test_engine_in_use_cannot_be_deleted(self):
        """引擎被级的 PROTECT 引用 → 友好提示，不是 500。"""
        save = Save.objects.create(name="生涯存档")
        rocket = Rocket.objects.create(name="火箭", program=save)
        engine = Engine.objects.get(name="引擎 A")
        RocketStage.objects.create(rocket=rocket, stage_order=1, engine=engine, structure_mass=0.1)
        response = self.client.post(
            reverse("parts:engine_list"),
            {"action": "delete", "pk": engine.pk, "confirmed": "yes"}, follow=True,
        )
        self.assertTrue(Engine.objects.filter(pk=engine.pk).exists())
        self.assertContains(response, "删除失败")


    def test_reference_pages_have_no_admin_link(self):
        for name in (
            "parts:engine_list", "parts:fueltank_list",
            "parts:instrument_list", "parts:body_list",
        ):
            with self.subTest(url_name=name):
                content = self.client.get(reverse(name)).content.decode()
                self.assertNotIn("/admin/", content)

    def test_reference_subnav_exists_and_highlights_current_page(self):
        """文档 11 §7.2：二级导航四项齐全，当前页高亮，其他项不高亮。"""
        content = self.client.get(reverse("parts:engine_list")).content.decode()
        subnav = content[content.index('class="bg-white border-bottom"'):content.index("<main")]
        for slug in ("engines", "fueltanks", "instruments", "bodies"):
            with self.subTest(slug=slug):
                self.assertIn(f'href="/reference/{slug}/"', subnav)
        self.assertIn("active", subnav_link(subnav, "/reference/engines/"))
        self.assertNotIn("active", subnav_link(subnav, "/reference/fueltanks/"))
        self.assertNotIn("active", subnav_link(subnav, "/reference/bodies/"))
        # 侧栏「参考数据」在参考数据的任何页面上都高亮
        self.assertIn("active", subnav_link(content, "/reference/engines/"))


