from django.db import transaction

from forecasting.models import Forecast, SkillGap
from planning.models import Alert, Recommendation


class PlanningDecisionEngine:
    """
    Converts forecasted labour-market gaps into ranked
    planner-facing alerts and recommendations.
    """

    def __init__(self, forecast_run=None):
        self.forecast_run = forecast_run

    def get_forecasts(self):
        queryset = Forecast.objects.select_related(
            "district",
            "district__state",
            "occupation",
            "occupation__sector",
            "run",
        ).prefetch_related("skill_gap")

        if self.forecast_run:
            queryset = queryset.filter(run=self.forecast_run)

        return queryset.order_by(
            "district__state__name",
            "district__name",
            "occupation__name",
            "forecast_month",
        )

    def get_alert_type(self, severity):
        if severity in ["critical_shortage", "shortage"]:
            return "shortage"

        if severity in ["critical_oversupply", "oversupply"]:
            return "oversupply"

        return None

    def calculate_persistence(self, forecast):
        """
        Measures how consistently the same district/occupation
        remains in the same gap direction across the forecast horizon.
        """

        forecasts = Forecast.objects.filter(
            run=forecast.run,
            district=forecast.district,
            occupation=forecast.occupation,
        )

        total = forecasts.count()

        if total == 0:
            return 0

        current_gap = forecast.skill_gap.gap_value

        if current_gap > 0:
            current_direction = "shortage"
        elif current_gap < 0:
            current_direction = "oversupply"
        else:
            return 0

        consistent = 0

        for item in forecasts:
            try:
                gap_value = item.skill_gap.gap_value
            except SkillGap.DoesNotExist:
                continue

            if gap_value > 0:
                item_direction = "shortage"
            elif gap_value < 0:
                item_direction = "oversupply"
            else:
                item_direction = "balanced"

            if item_direction == current_direction:
                consistent += 1

        return consistent / total

    def calculate_risk_score(self, forecast, skill_gap):
        """
        Composite risk score from 0-100.

        Factors:
        - gap magnitude
        - forecast confidence
        - persistence across forecast months
        """

        demand = max(forecast.predicted_demand, 0)
        supply = max(forecast.predicted_supply, 0)

        if demand <= 0 and supply <= 0:
            gap_ratio = 0
        else:
            denominator = max(demand, supply, 1)
            gap_ratio = abs(skill_gap.gap_value) / denominator

        gap_score = min(gap_ratio * 100, 100)

        confidence_score = min(
            max(forecast.confidence_score, 0),
            1,
        ) * 100

        persistence_score = (
            self.calculate_persistence(forecast) * 100
        )

        risk_score = (
            (gap_score * 0.50)
            + (confidence_score * 0.20)
            + (persistence_score * 0.30)
        )

        return round(
            min(max(risk_score, 0), 100),
            2,
        )

    def classify_risk(self, risk_score, skill_gap):
        """
        Converts the composite risk score into a planner-facing
        severity classification.

        Risk bands:
        0-39   -> balanced / monitor
        40-59  -> shortage / oversupply
        60-74  -> shortage / oversupply
        75+    -> critical shortage / critical oversupply
        """

        if skill_gap.gap_value > 0:
            if risk_score >= 75:
                return "critical_shortage"

            if risk_score >= 40:
                return "shortage"

            return "balanced"

        if skill_gap.gap_value < 0:
            if risk_score >= 75:
                return "critical_oversupply"

            if risk_score >= 40:
                return "oversupply"

            return "balanced"

        return "balanced"

    def get_alert_severity(self, skill_gap):
        if skill_gap.severity in [
            "critical_shortage",
            "critical_oversupply",
        ]:
            return "critical"

        if skill_gap.severity in [
            "shortage",
            "oversupply",
        ]:
            return "high"

        return "low"

    def build_alert_title(self, forecast, skill_gap):
        occupation = forecast.occupation.name
        district = forecast.district.name

        if skill_gap.severity == "critical_shortage":
            return f"Critical shortage risk: {occupation} in {district}"

        if skill_gap.severity == "shortage":
            return f"Emerging shortage: {occupation} in {district}"

        if skill_gap.severity == "critical_oversupply":
            return f"Critical oversupply risk: {occupation} in {district}"

        return f"Potential oversupply: {occupation} in {district}"

    def build_alert_message(self, forecast, skill_gap):
        occupation = forecast.occupation.name
        district = forecast.district.name

        gap = abs(skill_gap.gap_value)

        if skill_gap.gap_value > 0:
            action = "Training capacity may need to increase."
            direction = "exceeds projected worker supply"
        else:
            action = "Existing training capacity may need to be redirected."
            direction = "is below projected worker supply"

        return (
            f"{occupation} in {district} is projected to have "
            f"demand of approximately {forecast.predicted_demand:.0f} "
            f"against supply of approximately "
            f"{forecast.predicted_supply:.0f}. "
            f"The projected gap is approximately {gap:.0f}, "
            f"with demand {direction}. "
            f"Risk score: {skill_gap.risk_score:.1f}/100. "
            f"{action}"
        )

    def calculate_suggested_seats(self, forecast, skill_gap):
        if skill_gap.gap_value <= 0:
            return 0

        # Do not attempt to fill the entire projected gap immediately.
        # 75% provides a practical initial intervention target.
        suggested = skill_gap.gap_value * 0.75

        return max(
            1,
            round(suggested),
        )

    def build_recommendation(self, alert):
        forecast = alert.forecast
        skill_gap = forecast.skill_gap

        suggested_seats = self.calculate_suggested_seats(
            forecast,
            skill_gap,
        )

        if skill_gap.severity == "critical_shortage":
            recommendation_type = "launch_program"
            title = (
                f"Launch or rapidly expand "
                f"{forecast.occupation.name} training"
            )
            priority = "critical"

            explanation = (
                f"The forecast indicates a high-risk shortage of "
                f"{forecast.occupation.name} in "
                f"{forecast.district.name}. "
                f"The projected risk score is "
                f"{skill_gap.risk_score:.1f}/100. "
                f"Consider launching new training capacity or "
                f"rapidly expanding existing programmes."
            )

        elif skill_gap.severity == "shortage":
            recommendation_type = "increase_training"
            title = (
                f"Increase training capacity for "
                f"{forecast.occupation.name}"
            )
            priority = "high"

            explanation = (
                f"Projected demand exceeds available worker supply "
                f"for {forecast.occupation.name} in "
                f"{forecast.district.name}. "
                f"The current risk score is "
                f"{skill_gap.risk_score:.1f}/100. "
                f"Training capacity should be reviewed and increased "
                f"where feasible."
            )

        elif skill_gap.severity == "critical_oversupply":
            recommendation_type = "redirect_capacity"
            title = (
                f"Redirect excess {forecast.occupation.name} "
                f"training capacity"
            )
            priority = "critical"

            explanation = (
                f"The forecast indicates high-risk oversupply for "
                f"{forecast.occupation.name} in "
                f"{forecast.district.name}. "
                f"The projected risk score is "
                f"{skill_gap.risk_score:.1f}/100. "
                f"Consider redirecting training capacity toward "
                f"higher-demand occupations."
            )

            suggested_seats = 0

        elif skill_gap.severity == "oversupply":
            recommendation_type = "decrease_training"
            title = (
                f"Review training intake for "
                f"{forecast.occupation.name}"
            )
            priority = "high"

            explanation = (
                f"Projected worker supply exceeds labour demand for "
                f"{forecast.occupation.name} in "
                f"{forecast.district.name}. "
                f"The current risk score is "
                f"{skill_gap.risk_score:.1f}/100. "
                f"Future intake should be reviewed to avoid "
                f"further saturation."
            )

            suggested_seats = 0

        else:
            return None

        impact = abs(skill_gap.gap_percentage)

        estimated_impact = (
            f"Projected gap severity: {skill_gap.severity}. "
            f"Risk score: {skill_gap.risk_score:.1f}/100. "
            f"Estimated gap: {skill_gap.gap_value:.0f} workers "
            f"({impact:.1f}% of projected supply)."
        )

        return {
            "recommendation_type": recommendation_type,
            "title": title,
            "explanation": explanation,
            "suggested_seats": suggested_seats,
            "priority": priority,
            "estimated_impact": estimated_impact,
        }

    @transaction.atomic
    def generate(self):
        forecasts = self.get_forecasts()

        alerts_created = 0
        recommendations_created = 0
        alerts_updated = 0
        recommendations_updated = 0

        for forecast in forecasts:
            try:
                skill_gap = forecast.skill_gap
            except SkillGap.DoesNotExist:
                continue

            # Recalculate intelligence score.
            risk_score = self.calculate_risk_score(
                forecast,
                skill_gap,
            )

            new_severity = self.classify_risk(
                risk_score,
                skill_gap,
            )

            skill_gap.risk_score = risk_score
            skill_gap.severity = new_severity

            skill_gap.explanation = (
                f"Risk score combines projected gap magnitude, "
                f"forecast confidence, and persistence across the "
                f"forecast horizon. "
                f"Current score: {risk_score:.1f}/100."
            )

            skill_gap.save(
                update_fields=[
                    "risk_score",
                    "severity",
                    "explanation",
                ]
            )

            alert_type = self.get_alert_type(
                new_severity
            )

            if not alert_type:
                continue

            alert_severity = self.get_alert_severity(
                skill_gap
            )

            alert, created = Alert.objects.update_or_create(
                forecast=forecast,
                alert_type=alert_type,
                defaults={
                    "district": forecast.district,
                    "occupation": forecast.occupation,
                    "severity": alert_severity,
                    "title": self.build_alert_title(
                        forecast,
                        skill_gap,
                    ),
                    "message": self.build_alert_message(
                        forecast,
                        skill_gap,
                    ),
                },
            )

            if created:
                alerts_created += 1
            else:
                alerts_updated += 1

            recommendation_data = self.build_recommendation(
                alert
            )

            if not recommendation_data:
                continue

            _, recommendation_created = (
                Recommendation.objects.update_or_create(
                    alert=alert,
                    defaults={
                        "district": forecast.district,
                        "occupation": forecast.occupation,
                        **recommendation_data,
                    },
                )
            )

            if recommendation_created:
                recommendations_created += 1
            else:
                recommendations_updated += 1

        return {
            "forecasts_processed": forecasts.count(),
            "alerts_created": alerts_created,
            "alerts_updated": alerts_updated,
            "recommendations_created": recommendations_created,
            "recommendations_updated": recommendations_updated,
        }





