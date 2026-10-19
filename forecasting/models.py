from django.db import models
from labour.models import District, Occupation


class ForecastRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50, default="1.0")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    records_processed = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.model_name} v{self.model_version} - {self.status}"


class Forecast(models.Model):
    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name="forecasts"
    )
    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="forecasts"
    )
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="forecasts"
    )
    forecast_month = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)

    predicted_demand = models.FloatField(default=0)
    predicted_supply = models.FloatField(default=0)

    lower_demand = models.FloatField(null=True, blank=True)
    upper_demand = models.FloatField(null=True, blank=True)
    lower_supply = models.FloatField(null=True, blank=True)
    upper_supply = models.FloatField(null=True, blank=True)

    confidence_score = models.FloatField(default=0)
    horizon_months = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["-forecast_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "district", "occupation", "forecast_month"],
                name="unique_forecast_per_run_location_occupation_month"
            )
        ]
        indexes = [
            models.Index(fields=["district", "forecast_month"]),
            models.Index(fields=["occupation", "forecast_month"]),
            models.Index(fields=["forecast_month"]),
        ]

    @property
    def projected_gap(self):
        return round(self.predicted_demand - self.predicted_supply, 2)

    @property
    def demand_supply_ratio(self):
        if self.predicted_supply <= 0:
            return None
        return round(self.predicted_demand / self.predicted_supply, 2)

    def __str__(self):
        return f"{self.district} - {self.occupation} - {self.forecast_month}"


class SkillGap(models.Model):
    SEVERITY_CHOICES = [
        ("critical_shortage", "Critical Shortage"),
        ("shortage", "Shortage"),
        ("balanced", "Balanced"),
        ("oversupply", "Oversupply"),
        ("critical_oversupply", "Critical Oversupply"),
    ]

    forecast = models.OneToOneField(
        Forecast,
        on_delete=models.CASCADE,
        related_name="skill_gap"
    )

    gap_value = models.FloatField(default=0)
    gap_percentage = models.FloatField(default=0)
    severity = models.CharField(
        max_length=30,
        choices=SEVERITY_CHOICES,
        default="balanced"
    )
    risk_score = models.FloatField(default=0)

    explanation = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-risk_score"]

    def __str__(self):
        return f"{self.forecast} - {self.severity}"


class ModelPerformance(models.Model):
    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name="performance_metrics"
    )

    metric_name = models.CharField(max_length=50)
    metric_value = models.FloatField()
    evaluation_period = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["metric_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "metric_name"],
                name="unique_metric_per_forecast_run"
            )
        ]

    def __str__(self):
        return f"{self.run} - {self.metric_name}: {self.metric_value}"






