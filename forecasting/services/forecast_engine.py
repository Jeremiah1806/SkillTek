import math
from dataclasses import dataclass
from datetime import date

import numpy as np
from django.db import transaction
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from forecasting.models import ForecastRun, Forecast, SkillGap, ModelPerformance
from labour.models import LabourMarketSnapshot


@dataclass
class ForecastPoint:
    month: date
    demand: float
    supply: float


def safe_growth(current, previous):
    if previous is None or previous <= 0:
        return 0.0
    return (current - previous) / previous


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def smape(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    denominator = np.abs(actual) + np.abs(predicted)
    mask = denominator != 0

    if not np.any(mask):
        return 0.0

    return float(
        np.mean(
            2.0
            * np.abs(predicted[mask] - actual[mask])
            / denominator[mask]
        )
    )


def directional_accuracy(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    if len(actual) < 2 or len(predicted) < 2:
        return 0.0

    actual_direction = np.sign(np.diff(actual))
    predicted_direction = np.sign(np.diff(predicted))

    return float(np.mean(actual_direction == predicted_direction))


def calculate_reliability(smape_value, directional_value):
    error_component = clamp(1.0 - smape_value, 0.0, 1.0)
    direction_component = clamp(directional_value, 0.0, 1.0)

    return round(
        (0.70 * error_component) + (0.30 * direction_component),
        4,
    )


class LabourForecastEngine:
    def __init__(self):
        self.demand_model = RandomForestRegressor(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )

        self.supply_model = RandomForestRegressor(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )

    def calculate_trend_growth(self, values):
        if len(values) < 2:
            return 0.0

        recent = values[-1]
        previous = values[-2]

        return safe_growth(recent, previous)

    def calculate_seasonality(self, month_number):
        angle = 2 * math.pi * month_number / 12

        return (
            math.sin(angle),
            math.cos(angle),
        )

    def build_baseline(self, values, horizon):
        values = np.asarray(values, dtype=float)

        if len(values) == 0:
            return [0.0] * horizon

        if len(values) == 1:
            return [float(values[-1])] * horizon

        recent_window = values[-6:] if len(values) >= 6 else values

        x = np.arange(len(recent_window))
        slope, intercept = np.polyfit(x, recent_window, 1)

        future = []

        for step in range(1, horizon + 1):
            prediction = intercept + slope * (len(recent_window) - 1 + step)
            future.append(max(0.0, float(prediction)))

        return future

    def build_features(self, values, training_seats, hiring_index, month_number):
        values = list(values)

        while len(values) < 6:
            values.insert(0, values[0] if values else 0.0)

        growths = []

        for i in range(1, len(values)):
            growths.append(
                safe_growth(values[i], values[i - 1])
            )

        growths = growths[-5:]

        while len(growths) < 5:
            growths.insert(0, 0.0)

        trend = self.calculate_trend_growth(values)
        sin_month, cos_month = self.calculate_seasonality(month_number)

        return np.asarray(
            [
                *growths,
                trend,
                float(training_seats),
                float(hiring_index),
                sin_month,
                cos_month,
                float(values[-1]),
                float(np.mean(values[-3:])),
            ],
            dtype=float,
        )

    def build_growth_targets(self, values):
        values = list(values)

        features = []
        targets = []

        for i in range(6, len(values)):
            history = values[:i]

            growth = safe_growth(
                values[i],
                values[i - 1],
            )

            features.append(history)
            targets.append(growth)

        return features, targets

    def train_models(self, snapshots):
        demand_features = []
        demand_targets = []

        supply_features = []
        supply_targets = []

        grouped = {}

        for snapshot in snapshots:
            key = (
                snapshot.district_id,
                snapshot.occupation_id,
            )

            grouped.setdefault(key, []).append(snapshot)

        for rows in grouped.values():
            rows.sort(key=lambda row: row.month)

            demand_values = [
                float(row.job_demand)
                for row in rows
            ]

            supply_values = [
                float(row.worker_supply)
                for row in rows
            ]

            for i in range(6, len(rows)):
                demand_history = demand_values[:i]
                supply_history = supply_values[:i]

                row = rows[i]

                demand_features.append(
                    self.build_features(
                        demand_history,
                        row.training_seats,
                        row.industry_hiring_index,
                        row.month.month,
                    )
                )

                demand_targets.append(
                    safe_growth(
                        demand_values[i],
                        demand_values[i - 1],
                    )
                )

                supply_features.append(
                    self.build_features(
                        supply_history,
                        row.training_seats,
                        row.industry_hiring_index,
                        row.month.month,
                    )
                )

                supply_targets.append(
                    safe_growth(
                        supply_values[i],
                        supply_values[i - 1],
                    )
                )

        if demand_features:
            self.demand_model.fit(
                np.asarray(demand_features),
                np.asarray(demand_targets),
            )

        if supply_features:
            self.supply_model.fit(
                np.asarray(supply_features),
                np.asarray(supply_targets),
            )

    def build_single_feature(
        self,
        values,
        training_seats,
        hiring_index,
        month_number,
    ):
        return self.build_features(
            values,
            training_seats,
            hiring_index,
            month_number,
        )

    def predict_growth(
        self,
        model,
        values,
        training_seats,
        hiring_index,
        month_number,
    ):
        feature = self.build_single_feature(
            values,
            training_seats,
            hiring_index,
            month_number,
        ).reshape(1, -1)

        prediction = float(
            model.predict(feature)[0]
        )

        return clamp(
            prediction,
            -0.50,
            0.50,
        )

    def forecast_series(
        self,
        rows,
        horizon,
    ):
        rows = sorted(
            rows,
            key=lambda row: row.month,
        )

        demand_values = [
            float(row.job_demand)
            for row in rows
        ]

        supply_values = [
            float(row.worker_supply)
            for row in rows
        ]

        last_row = rows[-1]

        results = []

        last_month = last_row.month

        for step in range(1, horizon + 1):
            month_number = (
                last_month.month + step - 1
            ) % 12 + 1

            demand_growth = self.predict_growth(
                self.demand_model,
                demand_values,
                last_row.training_seats,
                last_row.industry_hiring_index,
                month_number,
            )

            supply_growth = self.predict_growth(
                self.supply_model,
                supply_values,
                last_row.training_seats,
                last_row.industry_hiring_index,
                month_number,
            )

            previous_demand = demand_values[-1]
            previous_supply = supply_values[-1]

            predicted_demand = max(
                0.0,
                previous_demand * (1 + demand_growth),
            )

            predicted_supply = max(
                0.0,
                previous_supply * (1 + supply_growth),
            )

            year = last_month.year
            month = last_month.month + step

            year += (month - 1) // 12
            month = (month - 1) % 12 + 1

            forecast_month = date(
                year,
                month,
                1,
            )

            results.append(
                ForecastPoint(
                    month=forecast_month,
                    demand=predicted_demand,
                    supply=predicted_supply,
                )
            )

            demand_values.append(predicted_demand)
            supply_values.append(predicted_supply)

        return results

    def evaluate_group(self, rows):
        rows = sorted(
            rows,
            key=lambda row: row.month,
        )

        if len(rows) < 10:
            return None

        split = int(len(rows) * 0.8)

        train_rows = rows[:split]
        test_rows = rows[split:]

        if len(test_rows) < 2:
            return None

        demand_history = [
            float(row.job_demand)
            for row in train_rows
        ]

        supply_history = [
            float(row.worker_supply)
            for row in train_rows
        ]

        actual_demand = []
        predicted_demand = []

        actual_supply = []
        predicted_supply = []

        for row in test_rows:
            demand_growth = self.predict_growth(
                self.demand_model,
                demand_history,
                row.training_seats,
                row.industry_hiring_index,
                row.month.month,
            )

            supply_growth = self.predict_growth(
                self.supply_model,
                supply_history,
                row.training_seats,
                row.industry_hiring_index,
                row.month.month,
            )

            demand_prediction = max(
                0.0,
                demand_history[-1] * (1 + demand_growth),
            )

            supply_prediction = max(
                0.0,
                supply_history[-1] * (1 + supply_growth),
            )

            actual_demand.append(
                float(row.job_demand)
            )

            predicted_demand.append(
                demand_prediction
            )

            actual_supply.append(
                float(row.worker_supply)
            )

            predicted_supply.append(
                supply_prediction
            )

            demand_history.append(
                float(row.job_demand)
            )

            supply_history.append(
                float(row.worker_supply)
            )

        return {
            "demand_mae": mean_absolute_error(
                actual_demand,
                predicted_demand,
            ),
            "demand_rmse": math.sqrt(
                mean_squared_error(
                    actual_demand,
                    predicted_demand,
                )
            ),
            "demand_r2": r2_score(
                actual_demand,
                predicted_demand,
            ),
            "demand_smape": smape(
                actual_demand,
                predicted_demand,
            ),
            "demand_directional_accuracy": directional_accuracy(
                actual_demand,
                predicted_demand,
            ),
            "supply_mae": mean_absolute_error(
                actual_supply,
                predicted_supply,
            ),
            "supply_rmse": math.sqrt(
                mean_squared_error(
                    actual_supply,
                    predicted_supply,
                )
            ),
            "supply_r2": r2_score(
                actual_supply,
                predicted_supply,
            ),
            "supply_smape": smape(
                actual_supply,
                predicted_supply,
            ),
            "supply_directional_accuracy": directional_accuracy(
                actual_supply,
                predicted_supply,
            ),
        }

    def evaluate(self, snapshots):
        grouped = {}

        for snapshot in snapshots:
            key = (
                snapshot.district_id,
                snapshot.occupation_id,
            )

            grouped.setdefault(key, []).append(snapshot)

        results = []

        for rows in grouped.values():
            metrics = self.evaluate_group(rows)

            if metrics:
                results.append(metrics)

        if not results:
            return {
                "demand_mae": 0.0,
                "demand_rmse": 0.0,
                "demand_r2": 0.0,
                "demand_smape": 0.0,
                "demand_directional_accuracy": 0.0,
                "supply_mae": 0.0,
                "supply_rmse": 0.0,
                "supply_r2": 0.0,
                "supply_smape": 0.0,
                "supply_directional_accuracy": 0.0,
                "reliability": 0.0,
            }

        keys = results[0].keys()

        averages = {
            key: float(
                np.mean(
                    [result[key] for result in results]
                )
            )
            for key in keys
        }

        demand_reliability = calculate_reliability(
            averages["demand_smape"],
            averages["demand_directional_accuracy"],
        )

        supply_reliability = calculate_reliability(
            averages["supply_smape"],
            averages["supply_directional_accuracy"],
        )

        averages["reliability"] = round(
            (demand_reliability + supply_reliability) / 2,
            4,
        )

        return averages

    def classify_gap(self, gap_percentage):
        if gap_percentage >= 30:
            return "critical_shortage"

        if gap_percentage >= 10:
            return "shortage"

        if gap_percentage <= -30:
            return "critical_oversupply"

        if gap_percentage <= -10:
            return "oversupply"

        return "balanced"

    @transaction.atomic
    def generate_forecasts(self, horizon=6):
        snapshots = list(
            LabourMarketSnapshot.objects.select_related(
                "district",
                "occupation",
            ).order_by(
                "district_id",
                "occupation_id",
                "month",
            )
        )

        run = ForecastRun.objects.create(
            model_name="SkillTek Hybrid Residual Forest",
            model_version="4.0",
            status="running",
            records_processed=len(snapshots),
        )

        try:
            self.train_models(snapshots)

            metrics = self.evaluate(snapshots)

            metric_names = [
                "demand_mae",
                "demand_rmse",
                "demand_r2",
                "demand_smape",
                "demand_directional_accuracy",
                "supply_mae",
                "supply_rmse",
                "supply_r2",
                "supply_smape",
                "supply_directional_accuracy",
                "reliability",
            ]

            for metric_name in metric_names:
                ModelPerformance.objects.create(
                    run=run,
                    metric_name=metric_name,
                    metric_value=metrics[metric_name],
                    evaluation_period="chronological 80/20 holdout",
                )

            grouped = {}

            for snapshot in snapshots:
                key = (
                    snapshot.district_id,
                    snapshot.occupation_id,
                )

                grouped.setdefault(key, []).append(snapshot)

            created_count = 0

            for rows in grouped.values():
                if len(rows) < 6:
                    continue

                rows.sort(
                    key=lambda row: row.month
                )

                forecast_points = self.forecast_series(
                    rows,
                    horizon,
                )

                district = rows[-1].district
                occupation = rows[-1].occupation

                for index, point in enumerate(
                    forecast_points,
                    start=1,
                ):
                    forecast = Forecast.objects.create(
                        run=run,
                        district=district,
                        occupation=occupation,
                        forecast_month=point.month,
                        predicted_demand=point.demand,
                        predicted_supply=point.supply,
                        horizon_months=index,
                        confidence_score=metrics["reliability"],
                    )

                    gap = point.demand - point.supply

                    denominator = max(
                        abs(point.supply),
                        1.0,
                    )

                    gap_percentage = (
                        gap / denominator
                    ) * 100

                    severity = self.classify_gap(
                        gap_percentage
                    )

                    risk_score = clamp(
                        abs(gap_percentage),
                        0.0,
                        100.0,
                    )

                    explanation = (
                        f"Projected demand is "
                        f"{point.demand:.0f} while projected "
                        f"supply is {point.supply:.0f}, producing "
                        f"a projected gap of {gap:.0f}."
                    )

                    SkillGap.objects.create(
                        forecast=forecast,
                        gap_value=gap,
                        gap_percentage=gap_percentage,
                        severity=severity,
                        risk_score=risk_score,
                        explanation=explanation,
                    )

                    created_count += 1

            run.records_created = created_count
            run.status = "completed"
            run.completed_at = None
            run.save(
                update_fields=[
                    "records_created",
                    "status",
                    "completed_at",
                ]
            )

            return run

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.save(
                update_fields=[
                    "status",
                    "error_message",
                ]
            )

            raise





