from django.contrib.auth.models import User
from django.db import models
from labour.models import State, District


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles"
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles"
    )
    experience_years = models.PositiveSmallIntegerField(default=0)
    education = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    profile_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username




