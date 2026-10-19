from dataclasses import dataclass
from math import ceil

from django.db.models import Sum

from labour.models import TrainingCapacity
from forecasting.models import Forecast
from planning.models import PolicySimulation


@dataclass
class SimulationResult:
    current_training_seats: int
    proposed_training_seats: int
    additional_seats: int
    current_projected_supply: float
    projected_demand: float
    simulated_projected_supply: float
    current_gap: float
    simulated_gap: float
    gap_reduction: float
    improvement_percentage: float
    conversion_factor: float
    outcome: str
    recommended_additional_seats: int
    recommended_total_seats: int
    recommended_projected_supply: float
    recommended_gap: float


class PolicySimulationEngine:
    """
    Transparent policy what-if engine.

    The simulator assumes that only a proportion of additional
    training seats translate into additional projected labour supply.

    The same assumption is also used to calculate the approximate
    number of additional seats required to close a projected shortage.
    """

    DEFAULT_CONVERSION_FACTOR = 0.70

    def __init__(self, conversion_factor=None):
        self.conversion_factor = (
            conversion_factor
            if conversion_factor is not None
            else self.DEFAULT_CONVERSION_FACTOR
        )

    def get_current_training_seats(self, district, occupation):
        capacity = TrainingCapacity.objects.filter(
            training_centre__district=district,
            occupation=occupation,
            year=2026,
        ).aggregate(
            total_seats=Sum("seats"),
        )

        return capacity["total_seats"] or 0

    def calculate_recommended_intervention(
        self,
        current_training_seats,
        current_projected_supply,
        projected_demand,
    ):
        """
        Estimate the smallest additional training capacity required
        to close a projected shortage under the current conversion
        assumption.
        """

        current_gap = projected_demand - current_projected_supply

        if current_gap <= 0:
            return {
                "additional_seats": 0,
                "total_seats": current_training_seats,
                "projected_supply": round(
                    current_projected_supply,
                    2,
                ),
                "gap": round(
                    current_gap,
                    2,
                ),
            }

        if self.conversion_factor <= 0:
            return {
                "additional_seats": 0,
                "total_seats": current_training_seats,
                "projected_supply": round(
                    current_projected_supply,
                    2,
                ),
                "gap": round(
                    current_gap,
                    2,
                ),
            }

        recommended_additional_seats = ceil(
            current_gap / self.conversion_factor
        )

        recommended_supply_increase = (
            recommended_additional_seats
            * self.conversion_factor
        )

        recommended_projected_supply = (
            current_projected_supply
            + recommended_supply_increase
        )

        recommended_gap = (
            projected_demand
            - recommended_projected_supply
        )

        return {
            "additional_seats": recommended_additional_seats,
            "total_seats": (
                current_training_seats
                + recommended_additional_seats
            ),
            "projected_supply": round(
                recommended_projected_supply,
                2,
            ),
            "gap": round(
                recommended_gap,
                2,
            ),
        }

    def determine_outcome(self, current_gap, simulated_gap):
        if current_gap > 0:
            if simulated_gap > 0:
                return "shortage_reduced"

            if simulated_gap == 0:
                return "balanced"

            return "shortage_eliminated_oversupply"

        if current_gap < 0:
            if simulated_gap < 0:
                return "oversupply_reduced"

            if simulated_gap == 0:
                return "balanced"

            return "oversupply_eliminated_shortage"

        if simulated_gap > 0:
            return "shortage"

        if simulated_gap < 0:
            return "oversupply"

        return "balanced"

    def simulate(
        self,
        district,
        occupation,
        forecast,
        proposed_training_seats,
        user=None,
        save=True,
    ):
        proposed_training_seats = max(
            0,
            int(proposed_training_seats),
        )

        current_training_seats = self.get_current_training_seats(
            district,
            occupation,
        )

        current_projected_supply = float(
            forecast.predicted_supply
        )

        projected_demand = float(
            forecast.predicted_demand
        )

        current_gap = (
            projected_demand
            - current_projected_supply
        )

        additional_seats = max(
            0,
            proposed_training_seats
            - current_training_seats,
        )

        additional_supply = (
            additional_seats
            * self.conversion_factor
        )

        simulated_projected_supply = (
            current_projected_supply
            + additional_supply
        )

        simulated_gap = (
            projected_demand
            - simulated_projected_supply
        )

        gap_reduction = (
            current_gap
            - simulated_gap
        )

        if abs(current_gap) > 0:
            improvement_percentage = (
                gap_reduction
                / abs(current_gap)
            ) * 100
        else:
            improvement_percentage = 0

        outcome = self.determine_outcome(
            current_gap,
            simulated_gap,
        )

        recommended = self.calculate_recommended_intervention(
            current_training_seats=current_training_seats,
            current_projected_supply=current_projected_supply,
            projected_demand=projected_demand,
        )

        result = SimulationResult(
            current_training_seats=current_training_seats,
            proposed_training_seats=proposed_training_seats,
            additional_seats=additional_seats,
            current_projected_supply=round(
                current_projected_supply,
                2,
            ),
            projected_demand=round(
                projected_demand,
                2,
            ),
            simulated_projected_supply=round(
                simulated_projected_supply,
                2,
            ),
            current_gap=round(
                current_gap,
                2,
            ),
            simulated_gap=round(
                simulated_gap,
                2,
            ),
            gap_reduction=round(
                gap_reduction,
                2,
            ),
            improvement_percentage=round(
                improvement_percentage,
                2,
            ),
            conversion_factor=self.conversion_factor,
            outcome=outcome,
            recommended_additional_seats=(
                recommended["additional_seats"]
            ),
            recommended_total_seats=(
                recommended["total_seats"]
            ),
            recommended_projected_supply=(
                recommended["projected_supply"]
            ),
            recommended_gap=(
                recommended["gap"]
            ),
        )

        if save:
            authenticated_user = (
                user
                if getattr(
                    user,
                    "is_authenticated",
                    False,
                )
                else None
            )

            existing_simulation = (
                PolicySimulation.objects.filter(
                    created_by=authenticated_user,
                    district=district,
                    occupation=occupation,
                    forecast=forecast,
                    proposed_training_seats=proposed_training_seats,
                )
                .order_by("-created_at")
                .first()
            )

            simulation_data = {
                "current_training_seats": current_training_seats,
                "proposed_training_seats": proposed_training_seats,
                "current_projected_supply": current_projected_supply,
                "simulated_projected_supply": simulated_projected_supply,
                "current_gap": current_gap,
                "simulated_gap": simulated_gap,
                "improvement_percentage": improvement_percentage,
                "status": "completed",
            }

            if existing_simulation:
                for field, value in simulation_data.items():
                    setattr(
                        existing_simulation,
                        field,
                        value,
                    )

                existing_simulation.save(
                    update_fields=list(
                        simulation_data.keys()
                    )
                )

            else:
                PolicySimulation.objects.create(
                    created_by=authenticated_user,
                    district=district,
                    occupation=occupation,
                    forecast=forecast,
                    **simulation_data,
                )

        return result









