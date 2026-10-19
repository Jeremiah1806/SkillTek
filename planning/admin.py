from django.contrib import admin
from .models import Alert, Recommendation, PolicySimulation


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "district",
        "occupation",
        "alert_type",
        "severity",
        "is_resolved",
        "created_at",
    )
    list_filter = (
        "alert_type",
        "severity",
        "is_resolved",
        "district__state",
        "occupation__sector",
    )
    search_fields = (
        "title",
        "message",
        "district__name",
        "occupation__name",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "district",
        "occupation",
        "recommendation_type",
        "priority",
        "suggested_seats",
        "reviewed",
        "created_at",
    )
    list_filter = (
        "recommendation_type",
        "priority",
        "reviewed",
        "district__state",
        "occupation__sector",
    )
    search_fields = (
        "title",
        "explanation",
        "district__name",
        "occupation__name",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(PolicySimulation)
class PolicySimulationAdmin(admin.ModelAdmin):
    list_display = (
        "district",
        "occupation",
        "current_training_seats",
        "proposed_training_seats",
        "current_gap",
        "simulated_gap",
        "improvement_percentage",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "district__state",
        "occupation__sector",
    )
    search_fields = (
        "district__name",
        "occupation__name",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)





