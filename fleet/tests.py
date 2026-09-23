"""Δv 计算、级方向、PROTECT 与详情页测试（规格 §4.6、§7、§9）。"""

import math

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from core.constants import G0
from core.models import Body
from ops.models import Save
from parts.models import Engine, FuelTank
from services.orbital import stage_dry_mass, stage_fuel_mass, vehicle_delta_v

from .models import Payload, Rocket, RocketStage


class ThreeStageRocketMixin:
    """三级火箭：每级 1 台引擎（干重 1.0 t）+ 1 个燃料罐（干重 0.5 t，容量 1000 单位）+ 结构 0.2 t。

    于是每级干重 = 0.2 + 1.0 + 0.5 = 1.7 t，每级燃料 = 1000 × 0.005 = 5.0 t，每级总重 6.7 t。
    载荷 2.0 t ⇒ **起飞质量 = 3 × 6.7 + 2.0 = 22.1 t**。
    """

    PAYLOAD_MASS = 2.0
    STAGE_DRY = 1.7
    STAGE_FUEL = 5.0

    def setUp(self):
        self.save = Save.objects.create(name="测试存档")
        self.engine = Engine.objects.create(
            name="测试引擎", dry_mass=1.0, isp_asl=300, isp_vac=345
        )
        self.tank = FuelTank.objects.create(name="测试燃料罐", dry_mass=0.5, capacity=1000)
        self.rocket = Rocket.objects.create(name="测试火箭", program=self.save)
        for order in (1, 2, 3):
            RocketStage.objects.create(
                rocket=self.rocket, stage_order=order,
                engine=self.engine, engine_count=1,
                fuel_tank=self.tank, tank_count=1,
                structure_mass=0.2,
            )


class StageMassTests(ThreeStageRocketMixin, TestCase):
    def test_stage_dry_mass(self):
        stage = self.rocket.stages.get(stage_order=1)
        self.assertAlmostEqual(stage_dry_mass(stage), self.STAGE_DRY)

    def test_stage_fuel_mass(self):
        stage = self.rocket.stages.get(stage_order=1)
        self.assertAlmostEqual(stage_fuel_mass(stage), self.STAGE_FUEL)

    def test_stage_order_is_unique_per_rocket(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0)

    def test_engine_in_use_cannot_be_deleted(self):
        # 规格 §4.12：Engine → RocketStage.engine 是 PROTECT
        with self.assertRaises(ProtectedError):
            self.engine.delete()

    def test_fuel_tank_in_use_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.tank.delete()

    def test_deleting_rocket_cascades_to_its_stages(self):
        self.rocket.delete()
        self.assertFalse(RocketStage.objects.exists())


class DeltaVTests(ThreeStageRocketMixin, TestCase):
    def test_rows_are_ascending_by_stage_order(self):
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        self.assertEqual([r["stage_order"] for r in rows], [1, 2, 3])

    def test_stage_order_1_is_the_bottom_and_heaviest_stage(self):
        # ★ 规格 §4.6 最容易弄反的地方：1 = 最先点火的最下面一级
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        self.assertEqual(rows[0]["stage_order"], 1)
        self.assertGreater(rows[0]["m0"], rows[-1]["m0"])

    def test_m0_ladder_includes_everything_above(self):
        # 起飞：所有级 + 载荷；第 2 级点火时扔掉第 1 级；第 3 级点火时只剩载荷 + 自己
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        self.assertAlmostEqual(rows[0]["m0"], 22.1)
        self.assertAlmostEqual(rows[1]["m0"], 15.4)
        self.assertAlmostEqual(rows[2]["m0"], 8.7)
        self.assertAlmostEqual(rows[0]["mf"], 17.1)
        self.assertAlmostEqual(rows[2]["mf"], 3.7)

    def test_mass_closure(self):
        """规格 §7.1：质量闭合是发现「漏算某一级」最有效的手段。

        注意用 `[0]`（起飞级），不是 `[-1]` —— 列表按 stage_order **升序**。
        """
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        total_dry = sum(stage_dry_mass(s) for s in self.rocket.stages.all())
        total_fuel = sum(stage_fuel_mass(s) for s in self.rocket.stages.all())
        self.assertAlmostEqual(rows[0]["m0"], total_dry + total_fuel + self.PAYLOAD_MASS)
        self.assertAlmostEqual(rows[0]["m0"], 22.1)
        # 反面：最上一级的 m0 只含载荷 + 它自己
        self.assertNotAlmostEqual(rows[-1]["m0"], total_dry + total_fuel + self.PAYLOAD_MASS)

    def test_cumulative_is_running_sum_in_ascending_order(self):
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        running = 0.0
        for row in rows:
            running += row["delta_v"]
            self.assertAlmostEqual(row["cumulative"], running)
        self.assertAlmostEqual(
            rows[-1]["cumulative"], sum(r["delta_v"] for r in rows)
        )

    def test_first_stage_uses_sea_level_isp_others_use_vacuum(self):
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        self.assertAlmostEqual(
            rows[0]["delta_v"], self.engine.isp_asl * G0 * math.log(22.1 / 17.1)
        )
        self.assertAlmostEqual(
            rows[1]["delta_v"], self.engine.isp_vac * G0 * math.log(15.4 / 10.4)
        )
        self.assertAlmostEqual(
            rows[2]["delta_v"], self.engine.isp_vac * G0 * math.log(8.7 / 3.7)
        )

    def test_delta_v_does_not_use_local_gravity(self):
        """§9 负例 + §7.2：用 Mun 当地重力会偏 -83%，本实现必须明显大于它。"""
        mun = Body.objects.create(name="Mun", mu=6.513839e10, radius=200000)
        g_mun = mun.mu / mun.radius ** 2          # ≈ 1.6285 m/s²
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        for row in rows:
            isp = self.engine.isp_asl if row["stage_order"] == 1 else self.engine.isp_vac
            wrong = isp * g_mun * math.log(row["m0"] / row["mf"])
            self.assertNotAlmostEqual(row["delta_v"], wrong)
            self.assertGreater(row["delta_v"], wrong * 2)

    def test_stage_without_engine_has_no_dv_but_mass_still_counts(self):
        stage = self.rocket.stages.get(stage_order=3)
        stage.engine = None
        stage.save()
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        self.assertIsNone(rows[2]["delta_v"])
        self.assertIsNone(rows[2]["cumulative"])
        self.assertAlmostEqual(rows[2]["m0"], 7.7)      # 少一台引擎的干重 1.0 t
        self.assertAlmostEqual(rows[0]["m0"], 21.1)

    def test_stage_without_fuel_tank_has_no_dv_and_no_fuel_mass(self):
        stage = self.rocket.stages.get(stage_order=2)
        stage.fuel_tank = None
        stage.save()
        rows = vehicle_delta_v(self.rocket, self.PAYLOAD_MASS)
        self.assertIsNone(rows[1]["delta_v"])
        self.assertAlmostEqual(rows[1]["fuel_mass"], 0.0)

    def test_rocket_without_stages_returns_empty_list(self):
        empty = Rocket.objects.create(name="空火箭", program=self.save)
        self.assertEqual(vehicle_delta_v(empty, self.PAYLOAD_MASS), [])


class RocketDetailViewTests(ThreeStageRocketMixin, TestCase):
    def test_page_renders_stages_descending(self):
        """§4.6：页面降序渲染（最上级在顶部），Δv 升序累加。"""
        response = self.client.get(reverse("fleet:rocket_detail", args=[self.rocket.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("最先点火的起飞级", html)          # 方向提示必须存在
        table_html = html[html.index("<table"):]        # 只看表格，避开提示文字里的「第 1 级」
        self.assertLess(table_html.index("第 3 级"), table_html.index("第 1 级"))

    def test_page_shows_total_delta_v(self):
        rows = vehicle_delta_v(self.rocket)
        total = sum(r["delta_v"] for r in rows)
        response = self.client.get(reverse("fleet:rocket_detail", args=[self.rocket.pk]))
        self.assertContains(response, f"{total:.0f}")

    def test_page_for_rocket_without_stages(self):
        empty = Rocket.objects.create(name="空火箭", program=self.save)
        response = self.client.get(reverse("fleet:rocket_detail", args=[empty.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "还没有配置级")

    def test_payload_does_not_affect_page_delta_v(self):
        """页面按 payload_mass=0 计算（火箭与载荷无外键），本测试把这个已知取舍钉住。"""
        rows = vehicle_delta_v(self.rocket, 0.0)
        response = self.client.get(reverse("fleet:rocket_detail", args=[self.rocket.pk]))
        self.assertContains(response, f"{sum(r['delta_v'] for r in rows):.0f}")
        self.assertContains(response, "不含载荷质量")
