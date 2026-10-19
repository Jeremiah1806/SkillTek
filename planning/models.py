from django.contrib.auth.models import User
from django.db import models
from forecasting.models import Forecast, SkillGap
from labour.models import District, Occupation


class Alert(models.Model):
    ALERT_TYPES = [
        ("shortage", "Shortage"),
        ("oversupply", "Oversupply"),
        ("emerging", "Emerging Skill"),
        ("rapid_growth", "Rapid Demand Growth"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="labour_alerts"
    )
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="labour_alerts"
    )
    forecast = models.ForeignKey(
        Forecast,
        on_delete=models.CASCADE,
        related_name="alerts"
    )

    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="medium"
    )

    title = models.CharField(max_length=250)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["district", "severity"]),
            models.Index(fields=["occupation", "severity"]),
            models.Index(fields=["is_resolved"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.severity}"


class Recommendation(models.Model):
    RECOMMENDATION_TYPES = [
        ("increase_training", "Increase Training"),
        ("decrease_training", "Decrease Training"),
        ("launch_program", "Launch Training Program"),
        ("redirect_capacity", "Redirect Training Capacity"),
        ("monitor", "Monitor"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="recommendations"
    )
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="recommendations"
    )
    alert = models.ForeignKey(
        Alert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations"
    )

    recommendation_type = models.CharField(
        max_length=40,
        choices=RECOMMENDATION_TYPES
    )
    title = models.CharField(max_length=250)
    explanation = models.TextField()

    suggested_seats = models.IntegerField(default=0)
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="medium"
    )

    estimated_impact = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_recommendations"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class PolicySimulation(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("completed", "Completed"),
    ]

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policy_simulations"
    )

    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="policy_simulations"
    )
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="policy_simulations"
    )
    forecast = models.ForeignKey(
        Forecast,
        on_delete=models.CASCADE,
        related_name="policy_simulations"
    )

    current_training_seats = models.PositiveIntegerField(default=0)
    proposed_training_seats = models.PositiveIntegerField(default=0)

    current_projected_supply = models.FloatField(default=0)
    simulated_projected_supply = models.FloatField(default=0)

    current_gap = models.FloatField(default=0)
    simulated_gap = models.FloatField(default=0)

    improvement_percentage = models.FloatField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def additional_seats(self):
        return max(
            0,
            self.proposed_training_seats - self.current_training_seats
        )

    @property
    def gap_reduction(self):
        return round(
            self.current_gap - self.simulated_gap,
            2
        )

    def __str__(self):
        return (
            f"{self.district} - "
            f"{self.occupation} - "
            f"Simulation {self.id}"
        )






