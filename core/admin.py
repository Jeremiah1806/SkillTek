from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "state",
        "district",
        "experience_years",
        "education",
        "profile_completed",
        "updated_at",
    )
    list_filter = (
        "state",
        "district",
        "profile_completed",
    )
    search_fields = (
        "user__username",
        "user__email",
        "education",
        "bio",
    )
    ordering = ("-updated_at",)



