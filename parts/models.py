"""部件库（规格 §4.2–§4.4）。

三张**各自独立的平表** —— 没有超类、没有 1:1 继承，允许少量列重复（§3 约束 4）。
这些是查表数据，**不带存档**（不属于任何 Save）。
"""

from django.db import models


class FuelType(models.TextChoices):
    LF_OX = "LF_OX", "液体燃料+氧化剂"
    MONO = "MONO", "单元推进剂"
    XENON = "XENON", "氙气"
    SOLID = "SOLID", "固体燃料"
    OTHER = "OTHER", "其他"


class FuelTank(models.Model):
    """燃料罐（规格 §4.2）。"""

    name = models.CharField("名称", max_length=60, unique=True)
    diameter = models.FloatField("直径 (m)", null=True, blank=True)
    dry_mass = models.FloatField("干重 (t)", default=0)
    capacity = models.FloatField("燃料容量（单位）", default=0)
    fuel_type = models.CharField(
        "燃料类型", max_length=10, choices=FuelType, default=FuelType.LF_OX
    )
    cost = models.PositiveIntegerField("造价 (√)", default=0)

    class Meta:
        verbose_name = "燃料罐"
        verbose_name_plural = "燃料罐"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Engine(models.Model):
    """引擎（规格 §4.3）。"""

    name = models.CharField("名称", max_length=60, unique=True)
    diameter = models.FloatField("直径 (m)", null=True, blank=True)
    dry_mass = models.FloatField("干重 (t)", default=0)
    thrust_asl = models.FloatField("海平面推力 (kN)", default=0)
    thrust_vac = models.FloatField("真空推力 (kN)", default=0)
    isp_asl = models.FloatField("海平面比冲 (s)", default=0)
    isp_vac = models.FloatField("真空比冲 (s)", default=0)
    cost = models.PositiveIntegerField("造价 (√)", default=0)

    class Meta:
        verbose_name = "引擎"
        verbose_name_plural = "引擎"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ScienceInstrument(models.Model):
    """科学设备（规格 §4.4）。"""

    name = models.CharField("名称", max_length=60, unique=True)
    dry_mass = models.FloatField("干重 (t)", default=0)
    experiment_type = models.CharField("实验类型", max_length=40, blank=True)
    data_value = models.FloatField("基础数据量 (Mits)", default=0)
    is_repeatable = models.BooleanField("可重复使用", default=False)
    requires_crew = models.BooleanField("需要乘员", default=False)
    cost = models.PositiveIntegerField("造价 (√)", default=0)

    class Meta:
        verbose_name = "科学设备"
        verbose_name_plural = "科学设备"
        ordering = ["name"]

    def __str__(self):
        return self.name
