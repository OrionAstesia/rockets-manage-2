"""玩家存档与发射日志（规格 §4.10–§4.11）。

`Save` 是玩家的 KSP 存档，也是本系统所有数据的**根容器**：火箭、载荷、发射场、
航天器、发射日志全部通过必填外键挂在某个存档下（删存档即 CASCADE 清空其内容）。
"""

from django.core.exceptions import ValidationError
from django.db import models, transaction


class GameMode(models.TextChoices):
    CAREER = "CAREER", "生涯模式"
    SCIENCE = "SCIENCE", "科研模式"
    SANDBOX = "SANDBOX", "沙盒模式"


class FlightState(models.TextChoices):
    PLANNED = "PLANNED", "计划中"
    LAUNCHED = "LAUNCHED", "已发射"
    FAILED = "FAILED", "发射失败"
    CANCELLED = "CANCELLED", "已取消"


class Save(models.Model):
    """玩家存档（规格 §4.11）。1:n 的「1」端，没有链接表。"""

    name = models.CharField("存档名称", max_length=60, unique=True)
    start_date = models.DateField("开始日期", null=True, blank=True)
    game_mode = models.CharField(
        "存档模式", max_length=10, choices=GameMode, default=GameMode.CAREER
    )

    class Meta:
        verbose_name = "玩家存档"
        verbose_name_plural = "玩家存档"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """删存档 = 清空它的全部内容（规格 §4.11）。

        **必须先级联删除在轨航天器与发射日志，再删其余内容。** 原因：`FlightLog`
        以 PROTECT 引用 `Rocket` / `Payload` / `Site`，而这三个又会被存档级联删除；
        Django 的删除收集器只要看到「有 FlightLog 以 PROTECT 引用即将被删的对象」
        就抛 `ProtectedError`，**并不会**因为那个 FlightLog 自己也将被级联删除而放行。

        整体包在事务里：若某条**别的存档**的任务引用了本存档的火箭/发射场，
        级联仍会被 PROTECT 拦住，此时前面的清理会一起回滚，不会留下半删状态。
        """
        with transaction.atomic():
            self.spacecraft.all().delete()
            self.flights.all().delete()
            return super().delete(*args, **kwargs)


class FlightLog(models.Model):
    """发射日志与发射计划（规格 §4.10）。"""

    name = models.CharField("任务名称", max_length=60)
    state = models.CharField(
        "状态", max_length=10, choices=FlightState,
        default=FlightState.PLANNED, db_index=True,
    )
    planned_date = models.DateField("计划发射日期", null=True, blank=True, db_index=True)
    actual_date = models.DateField("实际发射日期", null=True, blank=True)
    rocket = models.ForeignKey(
        "fleet.Rocket", verbose_name="运载火箭",
        on_delete=models.PROTECT, related_name="flights",
    )
    payload = models.ForeignKey(
        "fleet.Payload", verbose_name="有效载荷",
        null=True, blank=True, on_delete=models.PROTECT, related_name="flights",
    )
    site = models.ForeignKey(
        "spaceflight.Site", verbose_name="发射场",
        on_delete=models.PROTECT, related_name="flights",
    )
    crew_count = models.PositiveIntegerField("乘员数", default=0)
    result_code = models.IntegerField(
        "结果编码", null=True, blank=True,
        help_text="留空=尚未执行；-1=任务失败（火箭工作正常，载荷/设计问题）；"
                  "0=成功；>0=第 n 级失效（值为失效的级序号）。",
    )
    rest_dv = models.IntegerField(
        "剩余 Δv (m/s)", null=True, blank=True,
        help_text="留空=未记录，与「剩余 0」语义不同。",
    )
    cost = models.PositiveIntegerField("任务成本 (√)", default=0)
    program = models.ForeignKey(
        Save, verbose_name="所属存档",
        on_delete=models.CASCADE, related_name="flights",
    )
    detail = models.TextField("任务详情", blank=True)

    class Meta:
        verbose_name = "发射日志"
        verbose_name_plural = "发射日志"
        ordering = ["-planned_date"]
        indexes = [models.Index(fields=["state", "planned_date"])]

    def __str__(self):
        return self.name

    def clean(self):
        """规格 §4.10 的三条校验。"""
        errors = {}
        if self.state == FlightState.PLANNED and self.actual_date is not None:
            errors["actual_date"] = "「计划中」的任务不能有实际发射日期。"
        if self.state in (FlightState.LAUNCHED, FlightState.FAILED) and self.actual_date is None:
            errors["actual_date"] = "「已发射」或「发射失败」必须填写实际发射日期。"
        if self.result_code is not None and self.result_code < -1:
            errors["result_code"] = "结果编码只能是 -1（失败）、0（成功）或正整数（第 n 级失效）。"
        if errors:
            raise ValidationError(errors)
