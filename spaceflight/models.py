"""发射场与在轨航天器（规格 §4.8–§4.9）。"""

from django.core.exceptions import ValidationError
from django.db import models


class CraftType(models.TextChoices):
    STATION = "STATION", "空间站"
    RELAY_SAT = "RELAY_SAT", "中继卫星"
    PROBE = "PROBE", "探测器"
    ROVER = "ROVER", "探测车"
    CREWED = "CREWED", "载人飞船"
    LANDER = "LANDER", "着陆器"
    OTHER = "OTHER", "其他"


class Situation(models.TextChoices):
    ORBITING = "ORBITING", "环绕轨道"
    LANDED = "LANDED", "已着陆"
    SPLASHED = "SPLASHED", "水面溅落"
    FLYING = "FLYING", "大气内飞行"
    ESCAPING = "ESCAPING", "逃逸中"
    DESTROYED = "DESTROYED", "已损毁"


class Site(models.Model):
    """发射场（规格 §4.8）。"""

    name = models.CharField("发射场名称", max_length=60, unique=True)
    program = models.ForeignKey(
        "ops.Save", verbose_name="所属存档",
        on_delete=models.CASCADE, related_name="sites",
    )
    body = models.ForeignKey(
        "core.Body", verbose_name="所在天体",
        on_delete=models.PROTECT, related_name="sites",
    )
    latitude = models.FloatField("纬度 (°)", null=True, blank=True)
    longitude = models.FloatField("经度 (°)", null=True, blank=True)
    max_mass = models.FloatField("最大起飞质量 (t)", null=True, blank=True)
    is_operational = models.BooleanField("可用", default=True)
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "发射场"
        verbose_name_plural = "发射场"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """西/南为负（规格 §4.8）。"""
        errors = {}
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            errors["latitude"] = "纬度必须在 -90 到 90 之间（南纬为负）。"
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            errors["longitude"] = "经度必须在 -180 到 180 之间（西经为负）。"
        if errors:
            raise ValidationError(errors)


class Spacecraft(models.Model):
    """在轨航天器（规格 §4.9）。

    `craft_type` 回答「这是什么东西」（基本不变），`situation` 回答「它现在在干什么」（会变）。
    """

    name = models.CharField("名称", max_length=60, unique=True)
    program = models.ForeignKey(
        "ops.Save", verbose_name="所属存档",
        on_delete=models.CASCADE, related_name="spacecraft",
    )
    craft_type = models.CharField(
        "航天器类型", max_length=14, choices=CraftType,
        default=CraftType.OTHER, db_index=True,
    )
    body = models.ForeignKey(
        "core.Body", verbose_name="所在天体",
        on_delete=models.PROTECT, related_name="spacecraft",
    )
    situation = models.CharField(
        "运行状态", max_length=10, choices=Situation, default=Situation.ORBITING
    )
    is_active = models.BooleanField("在役", default=True)
    crew_count = models.PositiveIntegerField("乘员数", default=0)
    sma = models.FloatField(
        "半长轴 (m)", null=True, blank=True,
        help_text="半长轴（天体中心到轨道），不是高度。Kerbin 半径 600 km，"
                  "所以 100 km 高的圆轨道 sma = 700000。",
    )
    eccentricity = models.FloatField("离心率", null=True, blank=True)
    inclination = models.FloatField("轨道倾角 (°)", null=True, blank=True)
    cached_period_sec = models.FloatField("周期快照 (s)", null=True, blank=True)
    source_flight = models.ForeignKey(
        "ops.FlightLog", verbose_name="来源发射",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="spacecraft",
    )
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "在轨航天器"
        verbose_name_plural = "在轨航天器"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """规格 §4.9 的三条校验。"""
        errors = {}
        if self.sma is not None:
            radius = self.body.radius if self.body_id else None
            if radius is not None and self.sma <= radius:
                errors["sma"] = (
                    f"半长轴必须大于天体半径（{self.body.name} 半径 {radius:g} m）。"
                    "注意 sma 是「天体中心到轨道」的距离，不是高度；"
                    "高度 = sma − 天体半径。"
                )
        if self.situation == Situation.ORBITING and self.eccentricity is not None:
            if not 0 <= self.eccentricity < 1:
                errors["eccentricity"] = "环绕轨道要求 0 ≤ 离心率 < 1（e ≥ 1 是双曲线/抛物线）。"
        if self.inclination is not None and not 0 <= self.inclination <= 180:
            errors["inclination"] = "轨道倾角必须在 0 到 180 度之间。"
        if errors:
            raise ValidationError(errors)
