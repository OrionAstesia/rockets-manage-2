"""部件库冒烟测试 + 参考数据页（改造文档 10 第 4.4 / 8.2 节）。"""

from django.test import TestCase
from django.urls import reverse

from core.models import Body
from fleet.models import Rocket, RocketStage
from ops.models import Save

from .models import Engine, FuelTank, FuelType, ScienceInstrument


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


class ReferencePageTests(TestCase):
    """改造文档 10 第 4.4 / 8.2 节：`/reference/` 三个可编辑区块 + 只读天体。"""

    def setUp(self):
        Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000, has_atmosphere=True)
        Engine.objects.create(name="引擎 A", diameter=1.25, dry_mass=1.5, isp_asl=85, isp_vac=345)
        Engine.objects.create(name="引擎 B")
        FuelTank.objects.create(name="燃料罐 A", capacity=800)
        ScienceInstrument.objects.create(name="温度计", dry_mass=0.005, data_value=8)

    def test_page_renders_with_group_counts(self):
        response = self.client.get(reverse("parts:reference"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "共 2 个引擎")
        self.assertContains(response, "共 1 个燃料罐")
        self.assertContains(response, "共 1 个科学设备")
        self.assertContains(response, "共 1 个（只读）")

    def test_bodies_are_read_only(self):
        content = self.client.get(reverse("parts:reference")).content.decode()
        self.assertIn("Kerbin", content)
        self.assertNotIn("/bodies/", content)          # 天体没有编辑/删除入口

    def test_engine_crud(self):
        response = self.client.post(
            reverse("parts:engine_create"),
            {
                "name": "新引擎", "diameter": "2.5", "dry_mass": "3",
                "thrust_asl": "200", "thrust_vac": "240", "isp_asl": "90",
                "isp_vac": "350", "cost": "1500",
            },
        )
        self.assertRedirects(response, reverse("parts:reference"))
        engine = Engine.objects.get(name="新引擎")
        self.assertEqual(engine.isp_vac, 350)

        response = self.client.post(
            reverse("parts:engine_update", args=[engine.pk]),
            {
                "name": "改过的引擎", "diameter": "2.5", "dry_mass": "3",
                "thrust_asl": "200", "thrust_vac": "240", "isp_asl": "90",
                "isp_vac": "355", "cost": "1500",
            },
        )
        engine.refresh_from_db()
        self.assertEqual(engine.name, "改过的引擎")
        self.assertEqual(engine.isp_vac, 355)

        response = self.client.post(
            reverse("parts:engine_delete", args=[engine.pk]), {"confirmed": "yes"},
        )
        self.assertRedirects(response, reverse("parts:reference"))
        self.assertFalse(Engine.objects.filter(pk=engine.pk).exists())

    def test_fueltank_and_instrument_crud(self):
        response = self.client.post(
            reverse("parts:fueltank_create"),
            {"name": "新罐", "diameter": "1.25", "dry_mass": "0.25", "capacity": "400",
             "fuel_type": "XENON", "cost": "300"},
        )
        self.assertRedirects(response, reverse("parts:reference"))
        self.assertEqual(FuelTank.objects.get(name="新罐").fuel_type, FuelType.XENON)

        response = self.client.post(
            reverse("parts:instrument_create"),
            {"name": "新设备", "dry_mass": "0.02", "experiment_type": "重力",
             "data_value": "12", "is_repeatable": "on", "requires_crew": "", "cost": "500"},
        )
        self.assertRedirects(response, reverse("parts:reference"))
        instrument = ScienceInstrument.objects.get(name="新设备")
        self.assertTrue(instrument.is_repeatable)
        self.assertFalse(instrument.requires_crew)

        self.client.post(reverse("parts:fueltank_delete", args=[FuelTank.objects.get(name="新罐").pk]), {"confirmed": "yes"})
        self.client.post(reverse("parts:instrument_delete", args=[instrument.pk]), {"confirmed": "yes"})
        self.assertFalse(FuelTank.objects.filter(name="新罐").exists())
        self.assertFalse(ScienceInstrument.objects.filter(pk=instrument.pk).exists())

    def test_engine_in_use_cannot_be_deleted(self):
        """引擎被级的 PROTECT 引用 → 友好提示，不是 500。"""
        save = Save.objects.create(name="生涯存档")
        rocket = Rocket.objects.create(name="火箭", program=save)
        engine = Engine.objects.get(name="引擎 A")
        RocketStage.objects.create(rocket=rocket, stage_order=1, engine=engine, structure_mass=0.1)
        response = self.client.post(
            reverse("parts:engine_delete", args=[engine.pk]), {"confirmed": "yes"}, follow=True,
        )
        self.assertTrue(Engine.objects.filter(pk=engine.pk).exists())
        self.assertContains(response, "删除失败")

    def test_reference_page_has_no_admin_link(self):
        content = self.client.get(reverse("parts:reference")).content.decode()
        self.assertNotIn("/admin/", content)

