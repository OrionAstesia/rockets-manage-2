"""发射场经纬度与航天器轨道参数的 clean() 校验 + 前台 CRUD（改造文档 10 第 8.2 节）。"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Body
from ops.models import Save

from .forms import SiteForm, SpacecraftForm
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


class SpaceflightCrudTests(TestCase):
    """改造文档 10 第 8.2 节：发射场与航天器的新增/编辑/删除、program 从 URL 注入。"""

    def setUp(self):
        self.save = Save.objects.create(name="生涯存档")
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)

    def test_forms_do_not_expose_program(self):
        self.assertNotIn("program", SiteForm().fields)
        self.assertNotIn("program", SpacecraftForm().fields)

    def test_new_pages_render(self):
        for url in (reverse("spaceflight:site_create"), reverse("spaceflight:spacecraft_create")):
            response = self.client.get(f"{url}?save={self.save.pk}")
            self.assertEqual(response.status_code, 200)

    def test_missing_save_param_is_rejected(self):
        for url in (reverse("spaceflight:site_create"), reverse("spaceflight:spacecraft_create")):
            response = self.client.post(url, {"name": "不该被创建"})
            self.assertRedirects(response, reverse("core:save_list"))
        self.assertFalse(Site.objects.exists())
        self.assertFalse(Spacecraft.objects.exists())

    def test_create_site_with_save_param(self):
        response = self.client.post(
            f"{reverse('spaceflight:site_create')}?save={self.save.pk}",
            {"name": "KSC", "body": self.body.pk, "latitude": "-0.1", "longitude": "74.6",
             "max_mass": "", "is_operational": "on", "note": ""},
        )
        self.assertRedirects(response, reverse("ops:save_sites", args=[self.save.pk]))
        site = Site.objects.get(name="KSC")
        self.assertEqual(site.program_id, self.save.pk)
        self.assertTrue(site.is_operational)

    def test_site_coordinate_error_shows_on_form(self):
        """模型 clean() 的经纬度校验要能显示在表单上，而不是 500。"""
        response = self.client.post(
            f"{reverse('spaceflight:site_create')}?save={self.save.pk}",
            {"name": "坏发射场", "body": self.body.pk, "latitude": "95", "longitude": "0",
             "max_mass": "", "is_operational": "on", "note": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "纬度必须在 -90 到 90 之间")
        self.assertFalse(Site.objects.exists())

    def test_create_spacecraft_with_save_param(self):
        response = self.client.post(
            f"{reverse('spaceflight:spacecraft_create')}?save={self.save.pk}",
            {"name": "100 km 圆轨", "craft_type": "PROBE", "body": self.body.pk,
             "situation": "ORBITING", "is_active": "on", "crew_count": "0",
             "sma": "700000", "eccentricity": "0", "inclination": "0",
             "cached_period_sec": "", "source_flight": "", "note": ""},
        )
        self.assertRedirects(response, reverse("ops:save_spacecraft", args=[self.save.pk]))
        craft = Spacecraft.objects.get(name="100 km 圆轨")
        self.assertEqual(craft.program_id, self.save.pk)
        self.assertEqual(craft.sma, 700000)

    def test_spacecraft_sma_below_radius_shows_on_form(self):
        """sma 不是高度：低于天体半径必须给中文提示。"""
        response = self.client.post(
            f"{reverse('spaceflight:spacecraft_create')}?save={self.save.pk}",
            {"name": "太低", "craft_type": "PROBE", "body": self.body.pk,
             "situation": "ORBITING", "is_active": "on", "crew_count": "0",
             "sma": "500000", "eccentricity": "0", "inclination": "0",
             "cached_period_sec": "", "source_flight": "", "note": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "半长轴")
        self.assertFalse(Spacecraft.objects.exists())

    def test_spacecraft_form_mentions_sma_help_text(self):
        response = self.client.get(
            f"{reverse('spaceflight:spacecraft_create')}?save={self.save.pk}"
        )
        self.assertContains(response, "半长轴（天体中心到轨道），不是高度")

    def test_update_and_delete_spacecraft(self):
        craft = Spacecraft.objects.create(name="旧航天器", program=self.save, body=self.body)
        response = self.client.post(
            reverse("spaceflight:spacecraft_update", args=[craft.pk]),
            {"name": "改过的航天器", "craft_type": "STATION", "body": self.body.pk,
             "situation": "LANDED", "is_active": "on", "crew_count": "3",
             "sma": "", "eccentricity": "", "inclination": "",
             "cached_period_sec": "", "source_flight": "", "note": ""},
        )
        self.assertRedirects(response, reverse("ops:save_spacecraft", args=[self.save.pk]))
        craft.refresh_from_db()
        self.assertEqual(craft.name, "改过的航天器")
        self.assertEqual(craft.craft_type, CraftType.STATION)
        self.assertEqual(craft.crew_count, 3)

        response = self.client.post(
            reverse("spaceflight:spacecraft_delete", args=[craft.pk]), {"confirmed": "yes"},
        )
        self.assertRedirects(response, reverse("ops:save_spacecraft", args=[self.save.pk]))
        self.assertFalse(Spacecraft.objects.filter(pk=craft.pk).exists())

    def test_update_and_delete_site(self):
        site = Site.objects.create(name="旧发射场", program=self.save, body=self.body)
        response = self.client.post(
            reverse("spaceflight:site_update", args=[site.pk]),
            {"name": "改过的发射场", "body": self.body.pk, "latitude": "10",
             "longitude": "20", "max_mass": "100", "is_operational": "", "note": ""},
        )
        site.refresh_from_db()
        self.assertEqual(site.name, "改过的发射场")
        self.assertFalse(site.is_operational)

        self.client.post(reverse("spaceflight:site_delete", args=[site.pk]), {"confirmed": "yes"})
        self.assertFalse(Site.objects.filter(pk=site.pk).exists())

