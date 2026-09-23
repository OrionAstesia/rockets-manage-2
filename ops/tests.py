"""存档、发射日志的校验与删除策略测试（规格 §4.10–§4.12、§9）。"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from core.models import Body
from fleet.models import Payload, Rocket, RocketStage
from spaceflight.models import Site, Spacecraft

from .models import FlightLog, FlightState, GameMode, Save


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
