from django.contrib import admin
from .models import ForecastRun, Forecast, SkillGap, ModelPerformance


@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = (
        "model_name",
        "model_version",
        "status",
        "started_at",
        "completed_at",
        "records_processed",
        "records_created",
    )
    list_filter = ("status", "model_name", "model_version")
    search_fields = ("model_name", "model_version", "error_message")
    date_hierarchy = "started_at"
    ordering = ("-started_at",)


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = (
        "district",
        "occupation",
        "forecast_month",
        "predicted_demand",
        "predicted_supply",
        "confidence_score",
        "horizon_months",
    )
    list_filter = (
        "district__state",
        "occupation__sector",
        "occupation",
        "forecast_month",
    )
    search_fields = (
        "district__name",
        "occupation__name",
    )
    date_hierarchy = "forecast_month"
    ordering = ("-forecast_month",)


@admin.register(SkillGap)
class SkillGapAdmin(admin.ModelAdmin):
    list_display = (
        "forecast",
        "gap_value",
        "gap_percentage",
        "severity",
        "risk_score",
    )
    list_filter = ("severity",)
    search_fields = (
        "forecast__district__name",
        "forecast__occupation__name",
        "explanation",
    )
    ordering = ("-risk_score",)


@admin.register(ModelPerformance)
class ModelPerformanceAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "metric_name",
        "metric_value",
        "evaluation_period",
    )
    list_filter = ("metric_name",)
    search_fields = ("metric_name", "evaluation_period")
    ordering = ("metric_name",)



