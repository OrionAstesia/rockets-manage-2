"""发射场经纬度与航天器轨道参数的 clean() 校验（规格 §4.8、§4.9、§9）。"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Body
from ops.models import Save

from .models import CraftType, Site, Situation, Spacecraft


class SiteCleanTests(TestCase):
    def setUp(self):
        self.save = Save.objects.create(name="测试存档")
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)

    def test_valid_coordinates_pass(self):
        Site(
            name="KSC", program=self.save, body=self.body, latitude=-0.1, longitude=74.6
        ).clean()

    def test_boundary_coordinates_pass(self):
        Site(name="北极", program=self.save, body=self.body, latitude=90, longitude=180).clean()
        Site(name="南极", program=self.save, body=self.body, latitude=-90, longitude=-180).clean()

    def test_null_coordinates_pass(self):
        Site(name="未知坐标", program=self.save, body=self.body).clean()

    def test_latitude_out_of_range(self):
        with self.assertRaises(ValidationError) as ctx:
            Site(name="坏纬度", program=self.save, body=self.body, latitude=95).clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_longitude_out_of_range(self):
        with self.assertRaises(ValidationError) as ctx:
            Site(name="坏经度", program=self.save, body=self.body, longitude=181).clean()
        self.assertIn("longitude", ctx.exception.message_dict)


class SpacecraftCleanTests(TestCase):
    def setUp(self):
        self.save = Save.objects.create(name="测试存档")
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)

    def test_100km_circular_orbit_passes(self):
        # sma 是半长轴（天体中心到轨道），700000 = 600000 半径 + 100000 高度
        Spacecraft(
            name="100 km 圆轨", program=self.save, body=self.body,
            sma=700000, eccentricity=0.0, inclination=0.0,
        ).clean()

    def test_sma_must_exceed_body_radius(self):
        with self.assertRaises(ValidationError) as ctx:
            Spacecraft(name="太低", program=self.save, body=self.body, sma=500000).clean()
        self.assertIn("sma", ctx.exception.message_dict)
        self.assertIn("半长轴", ctx.exception.message_dict["sma"][0])

    def test_sma_without_body_radius_skips_check(self):
        body = Body.objects.create(name="无半径天体")
        Spacecraft(name="未知", program=self.save, body=body, sma=1).clean()

    def test_orbiting_with_hyperbolic_eccentricity_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            Spacecraft(
                name="坏轨道", program=self.save, body=self.body,
                situation=Situation.ORBITING, eccentricity=1.5,
            ).clean()
        self.assertIn("eccentricity", ctx.exception.message_dict)

    def test_escaping_may_have_hyperbolic_eccentricity(self):
        Spacecraft(
            name="逃逸中", program=self.save, body=self.body,
            situation=Situation.ESCAPING, sma=700000, eccentricity=1.5,
        ).clean()

    def test_inclination_range(self):
        with self.assertRaises(ValidationError) as ctx:
            Spacecraft(
                name="坏倾角", program=self.save, body=self.body, inclination=200
            ).clean()
        self.assertIn("inclination", ctx.exception.message_dict)
        Spacecraft(
            name="极轨", program=self.save, body=self.body, inclination=180
        ).clean()

    def test_craft_type_and_situation_are_independent(self):
        """探测器可以先环绕、后着陆 —— 两者不该混用（规格 §4.9）。"""
        probe = Spacecraft(
            name="探测器", program=self.save, body=self.body,
            craft_type=CraftType.PROBE, situation=Situation.ORBITING,
        )
        probe.clean()
        probe.situation = Situation.LANDED
        probe.clean()
        self.assertEqual(probe.craft_type, CraftType.PROBE)

    def test_craft_type_has_seven_choices(self):
        self.assertEqual(len(CraftType.choices), 7)
        self.assertEqual(CraftType.STATION.label, "空间站")
