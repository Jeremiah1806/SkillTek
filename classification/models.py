from django.contrib.auth.models import User
from django.db import models
from labour.models import Sector, Occupation


class UserOccupationProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="occupation_profile"
    )
    raw_occupation = models.CharField(max_length=300)
    raw_sector = models.CharField(max_length=200, blank=True)

    classified_sector = models.ForeignKey(
        Sector,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classified_user_profiles"
    )
    classified_occupation = models.ForeignKey(
        Occupation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classified_user_profiles"
    )

    confidence_score = models.FloatField(default=0)
    classification_method = models.CharField(
        max_length=50,
        default="ai"
    )
    classification_confirmed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.raw_occupation}"


class ClassificationRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="classification_requests"
    )

    occupation_profile = models.ForeignKey(
        UserOccupationProfile,
        on_delete=models.CASCADE,
        related_name="requests"
    )

    requested_sector = models.CharField(max_length=200, blank=True)
    requested_occupation = models.CharField(max_length=300)
    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    reviewer_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_classification_requests"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.requested_occupation}"



