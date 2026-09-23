from django.db import models


class Body(models.Model):
    """天体（规格 §4.1）。"""

    name = models.CharField("天体名称", max_length=30, unique=True)
    mu = models.FloatField("标准重力参数 (m³/s²)", null=True, blank=True)
    radius = models.FloatField("半径 (m)", null=True, blank=True)
    has_atmosphere = models.BooleanField("有大气", default=False)

    class Meta:
        verbose_name = "天体"
        verbose_name_plural = "天体"
        ordering = ["id"]

    def __str__(self):
        return self.name
