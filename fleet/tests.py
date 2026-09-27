"""Δv 计算、级方向、PROTECT 与详情页测试（规格 §4.6、§7、§9）。"""

import math

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from core.constants import G0
from core.models import Body
from ops.models import FlightLog, Save
from parts.models import Engine, FuelTank
from services.orbital import stage_dry_mass, stage_fuel_mass, vehicle_delta_v
from spaceflight.models import Site

from .forms import PayloadForm, RocketForm, StageForm
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


class SaveScopedDialogTests(TestCase):
    """火箭与载荷的弹窗增删改：POST 回存档的列表页，靠 action 分流（文档 12 第 4 / 8 节）。"""

    def setUp(self):
        self.save = Save.objects.create(name="生涯存档")
        self.other = Save.objects.create(name="另一个存档")
        self.rockets_url = reverse("ops:save_rockets", args=[self.save.pk])
        self.payloads_url = reverse("ops:save_payloads", args=[self.save.pk])

    def rocket_payload(self, prefix="new", **overrides):
        """带前缀的表单字段（和浏览器提交的一致）。"""
        data = {
            "name": "新火箭", "series": "K", "manufacturer": "", "diameter": "1.25",
            "first_flight_date": "", "crew_capacity": "0", "cost": "100", "note": "",
        }
        data.update(overrides)
        return {f"{prefix}-{key}": value for key, value in data.items()}

    def test_forms_do_not_expose_program(self):
        self.assertNotIn("program", RocketForm().fields)
        self.assertNotIn("program", PayloadForm().fields)

    def test_create_rocket_from_dialog(self):
        response = self.client.post(
            self.rockets_url, {"action": "create", "prefix": "new", **self.rocket_payload()},
        )
        self.assertRedirects(response, self.rockets_url)
        self.assertEqual(Rocket.objects.get(name="新火箭").program_id, self.save.pk)

    def test_update_cannot_move_object_to_another_program(self):
        """program 取自实例：即使提交里塞了别的存档，也改不走。"""
        rocket = Rocket.objects.create(name="火箭", program=self.save)
        response = self.client.post(
            self.rockets_url,
            {
                "action": "update", "pk": rocket.pk, "prefix": f"e{rocket.pk}",
                **self.rocket_payload(prefix=f"e{rocket.pk}", name="改名了", program=self.other.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        rocket.refresh_from_db()
        self.assertEqual(rocket.name, "改名了")
        self.assertEqual(rocket.program_id, self.save.pk)

    def test_model_save_method_still_works(self):
        """program 命名铁律的守卫：objects.create 与 instance.save() 都不能抛 TypeError。"""
        rocket = Rocket.objects.create(name="回归用火箭", program=self.save)
        rocket.series = "改一下"
        rocket.save()
        self.assertEqual(Rocket.objects.get(pk=rocket.pk).series, "改一下")

    def test_delete_rocket_from_dialog(self):
        rocket = Rocket.objects.create(name="要删的火箭", program=self.save)
        response = self.client.post(
            self.rockets_url, {"action": "delete", "pk": rocket.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, self.rockets_url)
        self.assertFalse(Rocket.objects.filter(pk=rocket.pk).exists())

    def test_delete_rocket_blocked_when_it_has_flights(self):
        """被 FlightLog 以 PROTECT 引用的火箭：友好提示，不是 500。"""
        body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        rocket = Rocket.objects.create(name="有任务的火箭", program=self.save)
        site = Site.objects.create(name="发射场", program=self.save, body=body)
        FlightLog.objects.create(name="任务", rocket=rocket, site=site, program=self.save)
        response = self.client.post(
            self.rockets_url, {"action": "delete", "pk": rocket.pk, "confirmed": "yes"},
            follow=True,
        )
        self.assertTrue(Rocket.objects.filter(pk=rocket.pk).exists())
        self.assertContains(response, "删除失败")

    def test_rockets_page_delete_dialog_mentions_stages(self):
        Rocket.objects.create(name="三级火箭", program=self.save)
        content = self.client.get(self.rockets_url).content.decode()
        self.assertIn("它的级会一并删除", content)

    def test_payload_crud_from_dialogs(self):
        response = self.client.post(
            self.payloads_url,
            {
                "action": "create", "prefix": "new",
                "new-name": "新载荷", "new-payload_type": "PROBE", "new-mass": "0.5",
                "new-diameter": "", "new-crew_capacity": "0", "new-cost": "0", "new-note": "",
            },
        )
        self.assertRedirects(response, self.payloads_url)
        payload = Payload.objects.get(name="新载荷")
        self.assertEqual(payload.program_id, self.save.pk)

        response = self.client.post(
            self.payloads_url, {"action": "delete", "pk": payload.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, self.payloads_url)
        self.assertFalse(Payload.objects.exists())


class StageDialogTests(TestCase):
    """级的弹窗增删改：POST 回火箭详情页，归属按 rocket 校验（文档 12 第 5.3 / 8 节）。"""

    def setUp(self):
        self.save = Save.objects.create(name="生涯存档")
        self.rocket = Rocket.objects.create(name="测试火箭", program=self.save)
        self.engine = Engine.objects.create(name="引擎", dry_mass=1.0, isp_asl=300, isp_vac=345)
        self.tank = FuelTank.objects.create(name="燃料罐", dry_mass=0.5, capacity=800)
        self.url = reverse("fleet:rocket_detail", args=[self.rocket.pk])

    def stage_payload(self, prefix="new", order=1, **overrides):
        data = {
            "stage_order": str(order), "engine": self.engine.pk, "engine_count": "1",
            "fuel_tank": self.tank.pk, "tank_count": "1", "structure_mass": "0.2",
            "separation_type": "STACK", "note": "",
        }
        data.update(overrides)
        return {f"{prefix}-{key}": value for key, value in data.items()}

    def test_create_stage_from_dialog(self):
        response = self.client.post(
            self.url, {"action": "create", "prefix": "new", **self.stage_payload(order=1)},
        )
        self.assertRedirects(response, self.url)
        self.assertEqual(RocketStage.objects.get(rocket=self.rocket).stage_order, 1)

    def test_form_suggests_next_stage_order(self):
        RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        RocketStage.objects.create(rocket=self.rocket, stage_order=2, structure_mass=0.1)
        self.assertEqual(StageForm(rocket=self.rocket).initial["stage_order"], 3)

    def test_first_stage_suggestion_starts_at_one(self):
        self.assertEqual(StageForm(rocket=self.rocket).initial["stage_order"], 1)

    def test_duplicate_stage_order_reopens_dialog_with_chinese_error(self):
        """重复序号要给中文提示并让弹窗重新打开，而不是 IntegrityError 500。"""
        RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        response = self.client.post(
            self.url, {"action": "create", "prefix": "new", **self.stage_payload(order=1)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "这枚火箭已经有第 1 级了")
        self.assertContains(response, 'data-open="1"')
        self.assertEqual(RocketStage.objects.count(), 1)

    def test_update_stage_from_dialog(self):
        stage = RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        response = self.client.post(
            self.url,
            {"action": "update", "pk": stage.pk, "prefix": f"e{stage.pk}",
             **self.stage_payload(prefix=f"e{stage.pk}", order=2)},
        )
        self.assertRedirects(response, self.url)
        stage.refresh_from_db()
        self.assertEqual(stage.stage_order, 2)

    def test_update_stage_keeping_its_own_order_is_allowed(self):
        """唯一性校验必须排除自身，否则原样保存就会报错。"""
        stage = RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        response = self.client.post(
            self.url,
            {"action": "update", "pk": stage.pk, "prefix": f"e{stage.pk}",
             **self.stage_payload(prefix=f"e{stage.pk}", order=1)},
        )
        self.assertRedirects(response, self.url)

    def test_delete_stage_from_dialog(self):
        stage = RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        response = self.client.post(
            self.url, {"action": "delete", "pk": stage.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, self.url)
        self.assertFalse(RocketStage.objects.exists())

    def test_detail_page_has_stage_dialogs(self):
        stage = RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        content = self.client.get(self.url).content.decode()
        self.assertIn('id="dlg-new"', content)
        self.assertIn(f'data-open-dialog="dlg-edit-{stage.pk}"', content)
        self.assertIn(f'data-open-dialog="dlg-del-{stage.pk}"', content)

    def test_cross_rocket_stage_update_is_refused(self):
        """拿别的火箭的级 pk 来改 → 拒绝，对方数据不变（文档 12 §8.2）。"""
        other_rocket = Rocket.objects.create(name="别人的火箭", program=self.save)
        other_stage = RocketStage.objects.create(
            rocket=other_rocket, stage_order=1, structure_mass=0.1,
        )
        response = self.client.post(
            self.url,
            {"action": "update", "pk": other_stage.pk, "prefix": f"e{other_stage.pk}",
             **self.stage_payload(prefix=f"e{other_stage.pk}", order=7)},
        )
        self.assertRedirects(response, self.url)
        other_stage.refresh_from_db()
        self.assertEqual(other_stage.stage_order, 1)

    def test_cross_rocket_stage_delete_is_refused(self):
        other_rocket = Rocket.objects.create(name="别人的火箭", program=self.save)
        other_stage = RocketStage.objects.create(
            rocket=other_rocket, stage_order=1, structure_mass=0.1,
        )
        response = self.client.post(
            self.url, {"action": "delete", "pk": other_stage.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, self.url)
        self.assertTrue(RocketStage.objects.filter(pk=other_stage.pk).exists())




class RocketDetailProgramTests(TestCase):
    """文档 10 第 4.3 / 8.2 节：修掉「所属存档」永远空白，并用测试卡住。"""

    def test_detail_page_shows_program_name_and_no_blank(self):
        save = Save.objects.create(name="我的生涯存档")
        rocket = Rocket.objects.create(name="火箭", program=save)
        response = self.client.get(reverse("fleet:rocket_detail", args=[rocket.pk]))
        self.assertContains(response, "我的生涯存档")   # 曾经写成 {{ rocket.save }}，永远是空白
        self.assertNotContains(response, "None")


