"""存档、发射日志的校验与删除策略测试（规格 §4.10–§4.12、§9）。"""

import re
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from core.models import Body
from fleet.models import Payload, Rocket, RocketStage
from spaceflight.models import Site, Spacecraft

from .forms import FlightLogForm
from .models import FlightLog, FlightState, GameMode, Save


def subnav_link(html, href):
    """取出指向 href 的 `<a>` 开标签（用来断言 active，不看别的活动元素）。"""
    match = re.search(r'<a[^>]*href="%s"[^>]*>' % re.escape(href), html)
    return match.group(0) if match else ""


class SaveModelTests(TestCase):
    def test_default_game_mode_is_career(self):
        self.assertEqual(Save.objects.create(name="新存档").game_mode, GameMode.CAREER)

    def test_game_mode_has_three_choices(self):
        self.assertEqual(len(GameMode.choices), 3)
        self.assertEqual(GameMode.SANDBOX.label, "沙盒模式")

    def test_name_is_globally_unique(self):
        Save.objects.create(name="存档 A")
        with self.assertRaises(Exception):
            Save.objects.create(name="存档 A")

    def test_model_save_method_is_not_shadowed(self):
        """规格 §4.11 的警告：外键必须叫 program，否则 Model.save() 被遮蔽。"""
        save = Save(name="用 Model.save() 存盘")
        save.save()
        self.assertIsNotNone(save.pk)


class FlightLogCleanTests(TestCase):
    """规格 §4.10 的三条校验。clean() 不碰外键，所以可以只构造不落库。"""

    def make(self, **kwargs):
        defaults = {"name": "任务", "state": FlightState.PLANNED}
        defaults.update(kwargs)
        return FlightLog(**defaults)

    def test_planned_must_not_have_actual_date(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make(state=FlightState.PLANNED, actual_date=date(2026, 1, 1)).clean()
        self.assertIn("actual_date", ctx.exception.message_dict)

    def test_planned_without_actual_date_is_fine(self):
        self.make(state=FlightState.PLANNED).clean()

    def test_launched_requires_actual_date(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make(state=FlightState.LAUNCHED).clean()
        self.assertIn("actual_date", ctx.exception.message_dict)

    def test_failed_requires_actual_date(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make(state=FlightState.FAILED).clean()
        self.assertIn("actual_date", ctx.exception.message_dict)

    def test_launched_with_actual_date_is_fine(self):
        self.make(state=FlightState.LAUNCHED, actual_date=date(2026, 1, 1)).clean()

    def test_cancelled_does_not_require_actual_date(self):
        self.make(state=FlightState.CANCELLED).clean()

    def test_result_code_below_minus_one_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make(result_code=-2).clean()
        self.assertIn("result_code", ctx.exception.message_dict)

    def test_valid_result_codes(self):
        for code in (None, -1, 0, 1, 3):
            self.make(result_code=code).clean()

    def test_rest_dv_zero_differs_from_null(self):
        # rest_dv 可空：NULL = 未记录，与「剩余 0」不同（§4.10）
        self.make(rest_dv=0).clean()
        self.make(rest_dv=None).clean()


class SaveDeletePolicyTests(TestCase):
    """规格 §4.12：Save → 五个子表是 CASCADE；Rocket/Payload/Site → FlightLog 是 PROTECT。"""

    def setUp(self):
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.save = Save.objects.create(name="要被删掉的存档", game_mode=GameMode.SANDBOX)
        self.rocket = Rocket.objects.create(name="测试火箭", program=self.save)
        self.payload = Payload.objects.create(name="测试载荷", program=self.save)
        self.site = Site.objects.create(name="测试发射场", program=self.save, body=self.body)
        self.flight = FlightLog.objects.create(
            name="测试任务", rocket=self.rocket, payload=self.payload,
            site=self.site, program=self.save,
        )
        self.spacecraft = Spacecraft.objects.create(
            name="测试航天器", program=self.save, body=self.body, source_flight=self.flight,
        )
        self.stage = RocketStage.objects.create(
            rocket=self.rocket, stage_order=1, structure_mass=1,
        )

    def test_deleting_save_cascades_to_everything_inside(self):
        self.save.delete()
        self.assertFalse(Save.objects.exists())
        self.assertFalse(Rocket.objects.exists())
        self.assertFalse(RocketStage.objects.exists())
        self.assertFalse(Payload.objects.exists())
        self.assertFalse(Site.objects.exists())
        self.assertFalse(Spacecraft.objects.exists())
        self.assertFalse(FlightLog.objects.exists())

    def test_delete_purges_spacecraft_and_flights_before_the_rest(self):
        """规格 §4.11：必须先删在轨航天器与发射日志，否则会被 PROTECT 挡住。"""
        self.save.delete()
        self.assertFalse(FlightLog.objects.exists())
        self.assertFalse(Spacecraft.objects.exists())
        self.assertFalse(Rocket.objects.exists())

    def test_delete_is_atomic_when_a_foreign_flight_blocks_it(self):
        """别的存档的任务引用了本存档的火箭 → 仍应被 PROTECT 拦住，且不留下半删状态。"""
        other = Save.objects.create(name="另一个存档")
        FlightLog.objects.create(
            name="跨存档任务", rocket=self.rocket, site=self.site, program=other
        )
        with self.assertRaises(ProtectedError):
            self.save.delete()
        self.assertTrue(Save.objects.filter(pk=self.save.pk).exists())
        self.assertTrue(FlightLog.objects.filter(program=self.save).exists())
        self.assertTrue(Spacecraft.objects.filter(program=self.save).exists())

    def test_rocket_used_by_flight_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.rocket.delete()

    def test_payload_used_by_flight_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.payload.delete()

    def test_site_used_by_flight_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.site.delete()

    def test_body_used_by_site_and_spacecraft_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.body.delete()

    def test_deleting_flight_sets_spacecraft_source_flight_to_null(self):
        self.flight.delete()
        self.spacecraft.refresh_from_db()
        self.assertIsNone(self.spacecraft.source_flight)

    def test_standalone_rocket_can_be_deleted_with_its_stages(self):
        self.flight.delete()          # 先解除 PROTECT
        self.rocket.delete()
        self.assertFalse(RocketStage.objects.filter(pk=self.stage.pk).exists())


class SchedulePageTests(TestCase):
    """规格 §8.2：/schedule/ 只列 state=PLANNED，按 planned_date 升序；空则显示空状态。"""

    def setUp(self):
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.save = Save.objects.create(name="生涯存档")
        self.rocket = Rocket.objects.create(name="火箭 A", program=self.save)
        self.site = Site.objects.create(name="发射场", program=self.save, body=self.body)

    def make_flight(self, name, state, planned_date):
        return FlightLog.objects.create(
            name=name, state=state, planned_date=planned_date,
            actual_date=None if state == FlightState.PLANNED else date(2026, 1, 1),
            rocket=self.rocket, site=self.site, program=self.save,
        )

    def test_only_planned_flights_in_ascending_order(self):
        self.make_flight("十月任务", FlightState.PLANNED, date(2026, 10, 10))
        self.make_flight("八月任务", FlightState.PLANNED, date(2026, 8, 5))
        self.make_flight("已发射任务", FlightState.LAUNCHED, date(2026, 7, 1))
        self.make_flight("失败任务", FlightState.FAILED, date(2026, 7, 2))
        self.make_flight("取消任务", FlightState.CANCELLED, date(2026, 7, 3))

        response = self.client.get(reverse("ops:schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [f.name for f in response.context["flights"]], ["八月任务", "十月任务"]
        )
        self.assertNotContains(response, "已发射任务")
        self.assertNotContains(response, "取消任务")

    def test_undated_planned_flight_sorts_last(self):
        self.make_flight("日期未定任务", FlightState.PLANNED, None)
        self.make_flight("八月任务", FlightState.PLANNED, date(2026, 8, 5))
        self.make_flight("十月任务", FlightState.PLANNED, date(2026, 10, 10))
        response = self.client.get(reverse("ops:schedule"))
        self.assertEqual(
            [f.name for f in response.context["flights"]],
            ["八月任务", "十月任务", "日期未定任务"],
        )

    def test_page_links_to_rocket_detail(self):
        self.make_flight("八月任务", FlightState.PLANNED, date(2026, 8, 5))
        response = self.client.get(reverse("ops:schedule"))
        self.assertContains(response, reverse("fleet:rocket_detail", args=[self.rocket.pk]))

    def test_empty_state(self):
        response = self.client.get(reverse("ops:schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "目前没有计划中的发射")


class SaveListPagesTests(TestCase):
    """文档 11 第 7.1 节：五类数据各自独立成页，每页只显示本存档的数据。"""

    def setUp(self):
        self.save_a = Save.objects.create(name="存档 A")
        self.save_b = Save.objects.create(name="存档 B")
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.rocket_a = Rocket.objects.create(name="A 的火箭", program=self.save_a)
        self.rocket_b = Rocket.objects.create(name="B 的火箭", program=self.save_b)
        self.site_a = Site.objects.create(name="A 的发射场", program=self.save_a, body=self.body)
        self.site_b = Site.objects.create(name="B 的发射场", program=self.save_b, body=self.body)
        FlightLog.objects.create(
            name="A 的任务", rocket=self.rocket_a, site=self.site_a, program=self.save_a,
        )
        self.flight_b = FlightLog.objects.create(
            name="B 的任务", rocket=self.rocket_b, site=self.site_b, program=self.save_b,
        )
        Spacecraft.objects.create(
            name="A 的航天器", program=self.save_a, body=self.body,
            sma=700000, eccentricity=0.0,
        )
        Spacecraft.objects.create(
            name="B 的航天器", program=self.save_b, body=self.body,
        )

    def test_all_five_pages_render(self):
        for name in (
            "save_rockets", "save_payloads", "save_sites", "save_spacecraft", "save_flights",
        ):
            with self.subTest(url_name=name):
                response = self.client.get(reverse(f"ops:{name}", args=[self.save_a.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "存档 A")

    def test_pages_are_program_scoped(self):
        """每页只出现本存档的数据（文档 11 §8.2「只显示本存档的数据」）。"""
        expectations = {
            "save_rockets": ("A 的火箭", "B 的火箭"),
            "save_sites": ("A 的发射场", "B 的发射场"),
            "save_spacecraft": ("A 的航天器", "B 的航天器"),
            "save_flights": ("A 的任务", "B 的任务"),
        }
        for name, (mine, others) in expectations.items():
            with self.subTest(url_name=name):
                response = self.client.get(reverse(f"ops:{name}", args=[self.save_a.pk]))
                self.assertContains(response, mine)
                self.assertNotContains(response, others)

    def test_payloads_page_is_program_scoped(self):
        Payload.objects.create(name="A 的载荷", program=self.save_a)
        Payload.objects.create(name="B 的载荷", program=self.save_b)
        response = self.client.get(reverse("ops:save_payloads", args=[self.save_a.pk]))
        self.assertContains(response, "A 的载荷")
        self.assertNotContains(response, "B 的载荷")

    def test_spacecraft_page_shows_period_computed_live(self):
        # Kerbin 100 km 圆轨：sma = 700000（= 600 km 半径 + 100 km 高度）→ 1958.128 s
        response = self.client.get(reverse("ops:save_spacecraft", args=[self.save_a.pk]))
        self.assertContains(response, "1,958.1 s")
        self.assertContains(response, "0.0909 Kerbin 天")

    def test_spacecraft_period_is_dash_when_not_computable(self):
        Spacecraft.objects.create(name="A 的未知轨道", program=self.save_a, body=self.body)
        response = self.client.get(reverse("ops:save_spacecraft", args=[self.save_a.pk]))
        rows = {row["obj"].name: row["period"] for row in response.context["rows"]}
        self.assertEqual(rows["A 的未知轨道"], "—")
        self.assertNotEqual(rows["A 的航天器"], "—")

    def test_flights_page_result_text(self):
        FlightLog.objects.create(
            name="失败任务", state=FlightState.FAILED, actual_date=date(2026, 1, 1),
            result_code=-1, rocket=self.rocket_a, site=self.site_a, program=self.save_a,
        )
        FlightLog.objects.create(
            name="三级失效任务", result_code=3,
            rocket=self.rocket_a, site=self.site_a, program=self.save_a,
        )
        response = self.client.get(reverse("ops:save_flights", args=[self.save_a.pk]))
        rows = {row["obj"].name: row["result"] for row in response.context["rows"]}
        self.assertEqual(rows["失败任务"], "失败")
        self.assertEqual(rows["三级失效任务"], "第 3 级失效")
        self.assertEqual(rows["A 的任务"], "—")

    def test_each_page_has_its_own_empty_state(self):
        empty = Save.objects.create(name="空存档")
        expectations = {
            "save_rockets": "还没有火箭",
            "save_payloads": "还没有载荷",
            "save_sites": "还没有发射场",
            "save_spacecraft": "还没有航天器",
            "save_flights": "还没有发射日志",
        }
        for name, text in expectations.items():
            with self.subTest(url_name=name):
                response = self.client.get(reverse(f"ops:{name}", args=[empty.pk]))
                self.assertContains(response, text)

    def test_each_page_has_exactly_one_table(self):
        """拆页回归：一页只显示一张表（文档 11 §8.2）。"""
        for name in (
            "save_rockets", "save_payloads", "save_sites", "save_spacecraft", "save_flights",
        ):
            with self.subTest(url_name=name):
                content = self.client.get(
                    reverse(f"ops:{name}", args=[self.save_a.pk])
                ).content.decode()
                self.assertEqual(content.count("<table"), 1)

    def test_rockets_page_does_not_show_other_sections(self):
        response = self.client.get(reverse("ops:save_rockets", args=[self.save_a.pk]))
        self.assertNotContains(response, "在轨航天器")

    def test_unknown_save_is_404(self):
        response = self.client.get(reverse("ops:save_rockets", args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_save_subnav_exists_and_highlights_current_page(self):
        content = self.client.get(
            reverse("ops:save_rockets", args=[self.save_a.pk])
        ).content.decode()
        subnav = content[content.index('class="bg-white border-bottom"'):content.index("<main")]
        slugs = ("rockets", "payloads", "sites", "spacecraft", "flights")
        for slug in slugs:
            with self.subTest(slug=slug):
                self.assertIn(f'href="/saves/{self.save_a.pk}/{slug}/"', subnav)
        self.assertIn("active", subnav_link(subnav, f"/saves/{self.save_a.pk}/rockets/"))
        self.assertNotIn("active", subnav_link(subnav, f"/saves/{self.save_a.pk}/payloads/"))
        # 侧栏「存档」在存档模块的任何页面上都高亮
        self.assertIn("active", subnav_link(content, "/saves/"))

    def test_no_admin_entry_anywhere(self):
        """文档 10 第 8.1 节：页面里没有「在后台编辑」按钮，导航里没有后台入口。"""
        for url in (
            reverse("core:home"),
            reverse("core:save_list"),
            reverse("ops:save_rockets", args=[self.save_a.pk]),
            reverse("ops:schedule"),
            reverse("fleet:rocket_detail", args=[self.rocket_a.pk]),
        ):
            content = self.client.get(url).content.decode()
            self.assertNotIn("在后台编辑", content)
            self.assertNotIn("/admin/", content)


class DialogProtocolTests(TestCase):
    """action 分流、缺参/非法参、以及跨存档越权（文档 12 第 4.2 / 8.2 节）。"""

    def setUp(self):
        self.save_a = Save.objects.create(name="存档 A")
        self.save_b = Save.objects.create(name="存档 B")
        self.rocket_a = Rocket.objects.create(name="A 的火箭", program=self.save_a)
        self.rocket_b = Rocket.objects.create(name="B 的火箭", program=self.save_b)
        self.url = reverse("ops:save_rockets", args=[self.save_a.pk])

    def test_missing_action_is_refused(self):
        response = self.client.post(self.url, {"name": "没有 action"})
        self.assertRedirects(response, self.url)
        self.assertEqual(Rocket.objects.count(), 2)          # 什么都没建

    def test_unknown_action_is_refused(self):
        response = self.client.post(self.url, {"action": "hack", "pk": self.rocket_a.pk})
        self.assertRedirects(response, self.url)
        self.assertTrue(Rocket.objects.filter(pk=self.rocket_a.pk).exists())

    def test_cross_save_update_is_refused(self):
        """拿别的存档的 pk 来改 → 拒绝，对方数据不变（防越权）。"""
        response = self.client.post(
            self.url,
            {"action": "update", "pk": self.rocket_b.pk, "prefix": f"e{self.rocket_b.pk}",
             f"e{self.rocket_b.pk}-name": "被篡改", f"e{self.rocket_b.pk}-series": "",
             f"e{self.rocket_b.pk}-manufacturer": "", f"e{self.rocket_b.pk}-diameter": "",
             f"e{self.rocket_b.pk}-first_flight_date": "",
             f"e{self.rocket_b.pk}-crew_capacity": "0", f"e{self.rocket_b.pk}-cost": "0",
             f"e{self.rocket_b.pk}-note": ""},
        )
        self.assertRedirects(response, self.url)
        self.rocket_b.refresh_from_db()
        self.assertEqual(self.rocket_b.name, "B 的火箭")

    def test_cross_save_delete_is_refused(self):
        response = self.client.post(
            self.url, {"action": "delete", "pk": self.rocket_b.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, self.url)
        self.assertTrue(Rocket.objects.filter(pk=self.rocket_b.pk).exists())

    def test_delete_without_confirmation_is_refused(self):
        response = self.client.post(self.url, {"action": "delete", "pk": self.rocket_a.pk})
        self.assertRedirects(response, self.url)
        self.assertTrue(Rocket.objects.filter(pk=self.rocket_a.pk).exists())



class FlightLogCrudTests(TestCase):
    """发射日志的弹窗增删改：POST 回列表页，靠 action 分流（文档 12 第 4 / 8 节）。"""

    def setUp(self):
        self.save = Save.objects.create(name="生涯存档")
        self.other = Save.objects.create(name="另一个存档")
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.rocket = Rocket.objects.create(name="本存档火箭", program=self.save)
        self.other_rocket = Rocket.objects.create(name="别人家的火箭", program=self.other)
        self.site = Site.objects.create(name="本存档发射场", program=self.save, body=self.body)
        self.url = reverse("ops:save_flights", args=[self.save.pk])

    def payload(self, prefix="new", **overrides):
        """按带前缀的表单字段名组装 POST 数据（和浏览器提交的一致）。"""
        data = {
            "name": "新任务", "state": FlightState.PLANNED, "planned_date": "2026-11-01",
            "actual_date": "", "rocket": self.rocket.pk, "payload": "", "site": self.site.pk,
            "crew_count": "0", "result_code": "", "rest_dv": "", "cost": "0", "detail": "",
        }
        data.update(overrides)
        return {f"{prefix}-{key}": value for key, value in data.items()}

    def test_all_five_list_pages_render_without_program_field(self):
        """五个列表页都带弹窗，且弹窗里没有「所属存档」字段（program 由页面带）。"""
        for name in (
            "save_rockets", "save_payloads", "save_sites", "save_spacecraft", "save_flights",
        ):
            with self.subTest(url_name=name):
                response = self.client.get(reverse(f"ops:{name}", args=[self.save.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "所属存档")

    def test_date_inputs_render_as_native_date_type(self):
        html = self.client.get(self.url).content.decode()
        # 空列表页只有「新增」弹窗，里面是 planned_date / actual_date 两个日期字段
        self.assertEqual(html.count('type="date"'), 2)
        self.assertNotIn('type="text" name="new-planned_date"', html)

    def test_form_has_no_program_field(self):
        self.assertNotIn("program", FlightLogForm().fields)

    def test_form_limits_fk_choices_to_the_program(self):
        form = FlightLogForm(program=self.save)
        self.assertIn(self.rocket, form.fields["rocket"].queryset)
        self.assertNotIn(self.other_rocket, form.fields["rocket"].queryset)

    def test_create_flight_from_dialog(self):
        response = self.client.post(
            self.url, {"action": "create", "prefix": "new", **self.payload()},
        )
        self.assertRedirects(response, self.url)
        self.assertEqual(FlightLog.objects.get(name="新任务").program_id, self.save.pk)

    def test_create_flight_invalid_state_date_reopens_dialog(self):
        """模型 clean() 的规则要显示在弹窗里（200 + data-open），而不是 500 / 302。"""
        response = self.client.post(
            self.url,
            {"action": "create", "prefix": "new",
             **self.payload(state=FlightState.LAUNCHED, actual_date="")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "必须填写实际发射日期")
        self.assertContains(response, 'data-open="1"')
        self.assertFalse(FlightLog.objects.exists())

    def test_update_flight_from_dialog(self):
        flight = FlightLog.objects.create(
            name="旧任务", rocket=self.rocket, site=self.site, program=self.save,
        )
        response = self.client.post(
            self.url,
            {"action": "update", "pk": flight.pk, "prefix": f"e{flight.pk}",
             **self.payload(prefix=f"e{flight.pk}", name="改过的任务")},
        )
        self.assertRedirects(response, self.url)
        flight.refresh_from_db()
        self.assertEqual(flight.name, "改过的任务")

    def test_delete_flight_from_dialog(self):
        flight = FlightLog.objects.create(
            name="要删的任务", rocket=self.rocket, site=self.site, program=self.save,
        )
        response = self.client.post(
            self.url, {"action": "delete", "pk": flight.pk, "confirmed": "yes"},
        )
        self.assertRedirects(response, self.url)
        self.assertFalse(FlightLog.objects.filter(pk=flight.pk).exists())



