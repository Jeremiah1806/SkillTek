from django.contrib import admin
from .models import (
    State,
    District,
    Sector,
    Occupation,
    OccupationAlias,
    TrainingCentre,
    TrainingCapacity,
    LabourMarketSnapshot,
    DataSource,
    DataImportRun,
)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "state")
    list_filter = ("state",)
    search_fields = ("name", "state__name")
    ordering = ("state__name", "name")


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code", "description")
    ordering = ("name",)


@admin.register(Occupation)
class OccupationAdmin(admin.ModelAdmin):
    list_display = ("name", "sector", "code", "skill_level", "active")
    list_filter = ("sector", "skill_level", "active")
    search_fields = ("name", "code", "description", "sector__name")
    ordering = ("sector__name", "name")


@admin.register(OccupationAlias)
class OccupationAliasAdmin(admin.ModelAdmin):
    list_display = ("name", "occupation", "source")
    list_filter = ("source",)
    search_fields = ("name", "occupation__name")
    ordering = ("name",)


@admin.register(TrainingCentre)
class TrainingCentreAdmin(admin.ModelAdmin):
    list_display = ("name", "centre_code", "district", "active")
    list_filter = ("district__state", "active")
    search_fields = ("name", "centre_code", "district__name")
    ordering = ("name",)


@admin.register(TrainingCapacity)
class TrainingCapacityAdmin(admin.ModelAdmin):
    list_display = (
        "training_centre",
        "occupation",
        "year",
        "seats",
        "enrolled",
        "completed",
    )
    list_filter = ("year", "occupation__sector", "occupation")
    search_fields = (
        "training_centre__name",
        "occupation__name",
    )
    ordering = ("-year", "occupation__name")


@admin.register(LabourMarketSnapshot)
class LabourMarketSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "district",
        "occupation",
        "month",
        "job_demand",
        "worker_supply",
        "training_seats",
        "industry_hiring_index",
        "demand_growth_rate",
    )
    list_filter = (
        "district__state",
        "occupation__sector",
        "occupation",
        "month",
    )
    search_fields = (
        "district__name",
        "occupation__name",
    )
    date_hierarchy = "month"
    ordering = ("-month",)


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "active")
    list_filter = ("source_type", "active")
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(DataImportRun)
class DataImportRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "status",
        "started_at",
        "completed_at",
        "records_processed",
        "records_created",
        "records_failed",
    )
    list_filter = ("status", "source")
    search_fields = ("error_message",)
    date_hierarchy = "started_at"
    ordering = ("-started_at",)





