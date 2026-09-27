"""界面外壳测试：弹窗与悬浮按钮的取舍、旧入口清理、空状态文案
（文档 12 第 8.2 节 + 文档 13 第 5 节）。

这些断言只看 HTML 外壳，不碰业务逻辑，所以集中放在这里；各 app 的 tests.py 只测自己的增删改。
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Body
from fleet.models import Rocket, RocketStage
from ops.models import Save
from spaceflight.models import Site


class ModalShellTests(TestCase):
    """JS 引入、每个列表页都有弹窗、FAB 该有的有/该没有的没有、旧入口已清掉。"""

    def setUp(self):
        self.save = Save.objects.create(name="生涯存档")
        self.body = Body.objects.create(name="Kerbin", mu=3.5316e12, radius=600000)
        self.rocket = Rocket.objects.create(name="测试火箭", program=self.save)
        RocketStage.objects.create(rocket=self.rocket, stage_order=1, structure_mass=0.1)
        self.site = Site.objects.create(name="发射场", program=self.save, body=self.body)

    def fab_pages(self):
        """应该有「新增」悬浮按钮的 10 个页面。"""
        return [
            reverse("core:save_list"),
            reverse("ops:save_rockets", args=[self.save.pk]),
            reverse("ops:save_payloads", args=[self.save.pk]),
            reverse("ops:save_sites", args=[self.save.pk]),
            reverse("ops:save_spacecraft", args=[self.save.pk]),
            reverse("ops:save_flights", args=[self.save.pk]),
            reverse("fleet:rocket_detail", args=[self.rocket.pk]),
            reverse("parts:engine_list"),
            reverse("parts:fueltank_list"),
            reverse("parts:instrument_list"),
        ]

    def test_modal_js_is_included(self):
        for url in (reverse("core:save_list"), reverse("fleet:rocket_detail", args=[self.rocket.pk])):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "js/modal.js")

    def test_every_fab_page_has_a_dialog_and_the_button(self):
        for url in self.fab_pages():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="dlg-new"')                    # 新建弹窗
                self.assertContains(response, 'data-open-dialog="dlg-new"')      # 悬浮按钮打开它
                self.assertContains(response, 'name="action"')                   # action 分流字段

    def test_fab_has_aria_label(self):
        self.assertContains(self.client.get(reverse("core:save_list")), 'aria-label="新增"')

    def test_fab_is_absent_where_there_is_nothing_to_add(self):
        """主页、发射日程、天体页（只读）：没有「新增」语义，右下角不放按钮。

        注意不能拿 `app-fab` 当判据 —— 那个类名也出现在 base.html 的 <style> 里，
        永远能匹配到。这里用按钮自身才有的 `data-open-dialog="dlg-new"`。
        """
        for url in (reverse("core:home"), reverse("ops:schedule"), reverse("parts:body_list")):
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), 'data-open-dialog="dlg-new"')

    def test_old_new_entry_links_are_gone(self):
        """旧的「右上角 + 新增 / + 新增一级」链接不该再出现。"""
        for url in self.fab_pages():
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                self.assertNotIn("+ 新增", content)
                self.assertNotIn("点右上角", content)


class EmptyStateWordingTests(TestCase):
    """空状态文案必须指向右下角的悬浮按钮（文档 13 §2.5 列了 10 处）。"""

    def setUp(self):
        self.save = Save.objects.create(name="空存档")

    def test_save_list_pages_point_to_the_corner_button(self):
        for name in (
            "save_rockets", "save_payloads", "save_sites", "save_spacecraft", "save_flights",
        ):
            with self.subTest(url_name=name):
                response = self.client.get(reverse(f"ops:{name}", args=[self.save.pk]))
                self.assertContains(response, "右下角")
                self.assertNotContains(response, "右上角")

    def test_reference_pages_point_to_the_corner_button(self):
        for name in ("parts:engine_list", "parts:fueltank_list", "parts:instrument_list"):
            with self.subTest(url_name=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, "右下角")
                self.assertNotContains(response, "右上角")

    def test_rocket_detail_points_to_the_corner_button(self):
        rocket = Rocket.objects.create(name="空火箭", program=self.save)
        response = self.client.get(reverse("fleet:rocket_detail", args=[rocket.pk]))
        self.assertContains(response, "右下角")
        self.assertNotContains(response, "右上角")

    def test_save_list_empty_state_does_not_mention_the_old_inline_form(self):
        Save.objects.all().delete()                  # 空状态只在真的没有存档时出现
        response = self.client.get(reverse("core:save_list"))
        self.assertContains(response, "还没有存档")
        self.assertContains(response, "右下角")
        self.assertNotContains(response, "上面的表单")
