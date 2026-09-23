"""运载火箭、火箭的级、有效载荷（规格 §4.5–§4.7）。

级**直接挂火箭**（`RocketStage.rocket`），没有多态外键、没有双可空 FK。
"""

from django.db import models


class SeparationType(models.TextChoices):
    STACK = "STACK", "堆叠分离"
    RADIAL = "RADIAL", "径向分离"
    NONE = "NONE", "不分离"


class PayloadType(models.TextChoices):
    CREW_CAPSULE = "CREW_CAPSULE", "载人舱"
    CARGO = "CARGO", "货运舱"
    SATELLITE = "SATELLITE", "卫星"
    PROBE = "PROBE", "探测器"
    LANDER = "LANDER", "着陆器"
    OTHER = "OTHER", "其他"


class Rocket(models.Model):
    """运载火箭（规格 §4.5）。"""

    name = models.CharField("火箭名称", max_length=60, unique=True)
    series = models.CharField("系列", max_length=40, blank=True)
    manufacturer = models.CharField("制造商", max_length=40, blank=True)
    diameter = models.FloatField("最大直径 (m)", null=True, blank=True)
    first_flight_date = models.DateField("首飞日期", null=True, blank=True)
    crew_capacity = models.PositiveIntegerField("乘员容量", default=0)
    cost = models.PositiveIntegerField("造价 (√)", default=0)
    is_reusable = models.BooleanField("可回收复用", default=False)
    # ★ 外键属性名必须是 program，不能叫 save：save 会遮蔽 Django 的 Model.save()
    #   （见规格 §4.11 的警告；manage.py check 与 makemigrations 都查不出来）
    program = models.ForeignKey(
        "ops.Save", verbose_name="所属存档",
        on_delete=models.CASCADE, related_name="rockets",
    )
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "运载火箭"
        verbose_name_plural = "运载火箭"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RocketStage(models.Model):
    """火箭的级（规格 §4.6）。

    ★ `stage_order` 方向约定：1 = **最先点火、最下面那一级**（起飞级），向上递增。
    渲染降序（最上级在顶部），Δv 计算升序累加 —— 见 §4.6 与 §7.1。
    """

    rocket = models.ForeignKey(
        Rocket, verbose_name="所属火箭",
        on_delete=models.CASCADE, related_name="stages",
    )
    stage_order = models.PositiveIntegerField("级序号")
    engine = models.ForeignKey(
        "parts.Engine", verbose_name="引擎",
        null=True, blank=True, on_delete=models.PROTECT, related_name="stages",
    )
    engine_count = models.PositiveIntegerField("引擎数量", default=1)
    fuel_tank = models.ForeignKey(
        "parts.FuelTank", verbose_name="燃料罐",
        null=True, blank=True, on_delete=models.PROTECT, related_name="stages",
    )
    tank_count = models.PositiveIntegerField("燃料罐数量", default=0)
    structure_mass = models.FloatField("结构质量 (t)", default=0)
    separation_type = models.CharField(
        "分离方式", max_length=10, choices=SeparationType, default=SeparationType.STACK
    )
    note = models.CharField("备注", max_length=100, blank=True)

    class Meta:
        verbose_name = "级"
        verbose_name_plural = "级"
        ordering = ["stage_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["rocket", "stage_order"], name="uniq_rocket_stage_order"
            ),
        ]

    def __str__(self):
        return f"{self.rocket.name} 第 {self.stage_order} 级"


class Payload(models.Model):
    """有效载荷（规格 §4.7）。载荷**不带级**（v1 明确不含）。"""

    name = models.CharField("载荷名称", max_length=60, unique=True)
    payload_type = models.CharField(
        "载荷类型", max_length=12, choices=PayloadType, default=PayloadType.OTHER
    )
    mass = models.FloatField("质量 (t)", default=0)
    diameter = models.FloatField("最小整流罩直径 (m)", null=True, blank=True)
    crew_capacity = models.PositiveIntegerField("乘员容量", default=0)
    has_docking_port = models.BooleanField("带对接端口", default=False)
    cost = models.PositiveIntegerField("造价 (√)", default=0)
    program = models.ForeignKey(
        "ops.Save", verbose_name="所属存档",
        on_delete=models.CASCADE, related_name="payloads",
    )
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "有效载荷"
        verbose_name_plural = "有效载荷"
        ordering = ["name"]

    def __str__(self):
        return self.name
