"""部件库冒烟测试（规格 §10 S2 完成标准：能在 Admin 录入引擎与燃料罐）。"""

from django.test import TestCase

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
