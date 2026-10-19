from django.contrib import admin
from .models import UserOccupationProfile, ClassificationRequest


@admin.register(UserOccupationProfile)
class UserOccupationProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "raw_occupation",
        "classified_sector",
        "classified_occupation",
        "confidence_score",
        "classification_method",
        "classification_confirmed",
        "updated_at",
    )
    list_filter = (
        "classification_method",
        "classification_confirmed",
        "classified_sector",
    )
    search_fields = (
        "user__username",
        "raw_occupation",
        "raw_sector",
        "classified_occupation__name",
        "classified_sector__name",
    )
    ordering = ("-updated_at",)


@admin.register(ClassificationRequest)
class ClassificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "requested_occupation",
        "requested_sector",
        "status",
        "reviewed_by",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status", "requested_sector")
    search_fields = (
        "user__username",
        "requested_occupation",
        "requested_sector",
        "reason",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)





