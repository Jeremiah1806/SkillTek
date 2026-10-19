from django.db import models


class State(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="districts")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["state__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["state", "name"], name="unique_district_per_state")
        ]

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Sector(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Occupation(models.Model):
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name="occupations")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    skill_level = models.PositiveSmallIntegerField(default=3)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sector__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["sector", "name"],
                name="unique_occupation_per_sector"
            )
        ]

    def __str__(self):
        return self.name


class OccupationAlias(models.Model):
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="aliases"
    )
    name = models.CharField(max_length=200)
    source = models.CharField(max_length=50, default="system")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["occupation", "name"],
                name="unique_occupation_alias"
            )
        ]

    def __str__(self):
        return f"{self.name} → {self.occupation.name}"


class TrainingCentre(models.Model):
    name = models.CharField(max_length=200)
    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="training_centres"
    )
    centre_code = models.CharField(max_length=50, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TrainingCapacity(models.Model):
    training_centre = models.ForeignKey(
        TrainingCentre,
        on_delete=models.CASCADE,
        related_name="capacities"
    )
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="training_capacities"
    )
    year = models.PositiveIntegerField()
    seats = models.PositiveIntegerField(default=0)
    enrolled = models.PositiveIntegerField(default=0)
    completed = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["training_centre", "occupation", "year"],
                name="unique_centre_occupation_year"
            )
        ]
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["occupation", "year"]),
        ]

    def __str__(self):
        return f"{self.training_centre.name} - {self.occupation.name} ({self.year})"


class LabourMarketSnapshot(models.Model):
    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        related_name="market_snapshots"
    )
    occupation = models.ForeignKey(
        Occupation,
        on_delete=models.CASCADE,
        related_name="market_snapshots"
    )
    month = models.DateField()
    job_demand = models.PositiveIntegerField(default=0)
    worker_supply = models.PositiveIntegerField(default=0)
    training_seats = models.PositiveIntegerField(default=0)
    industry_hiring_index = models.FloatField(default=0)
    demand_growth_rate = models.FloatField(default=0)

    class Meta:
        ordering = ["-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["district", "occupation", "month"],
                name="unique_market_snapshot"
            )
        ]
        indexes = [
            models.Index(fields=["district", "month"]),
            models.Index(fields=["occupation", "month"]),
            models.Index(fields=["month"]),
        ]

    @property
    def skill_gap(self):
        return self.job_demand - self.worker_supply

    @property
    def demand_supply_ratio(self):
        if self.worker_supply == 0:
            return 0
        return round(self.job_demand / self.worker_supply, 2)

    def __str__(self):
        return f"{self.district} - {self.occupation} - {self.month}"


class DataSource(models.Model):
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DataImportRun(models.Model):
    source = models.ForeignKey(
        DataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_runs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, default="pending")
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Import {self.id} - {self.status}"





