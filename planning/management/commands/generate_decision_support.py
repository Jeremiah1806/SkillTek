from django.core.management.base import BaseCommand
from forecasting.models import ForecastRun
from planning.services.decision_engine import PlanningDecisionEngine


class Command(BaseCommand):
    help = "Generate labour-market alerts and planner recommendations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--run",
            type=int,
            default=None,
            help="Forecast run ID to process. Defaults to the latest completed run.",
        )

    def handle(self, *args, **options):
        run_id = options["run"]

        if run_id:
            forecast_run = ForecastRun.objects.get(
                id=run_id,
                status="completed",
            )
        else:
            forecast_run = ForecastRun.objects.filter(
                status="completed"
            ).order_by("-id").first()

        if not forecast_run:
            self.stdout.write(
                self.style.ERROR(
                    "No completed forecast run was found."
                )
            )
            return

        self.stdout.write(
            f"Processing forecast run #{forecast_run.id}..."
        )

        engine = PlanningDecisionEngine(
            forecast_run=forecast_run
        )

        results = engine.generate()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Decision-support generation completed successfully."
            )
        )
        self.stdout.write(
            f"Forecasts processed: {results['forecasts_processed']}"
        )
        self.stdout.write(
            f"Alerts created: {results['alerts_created']}"
        )
        self.stdout.write(
            f"Recommendations created: {results['recommendations_created']}"
        )





