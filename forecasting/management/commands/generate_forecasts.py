from django.core.management.base import BaseCommand
from forecasting.services.forecast_engine import LabourForecastEngine


class Command(BaseCommand):
    help = "Generate labour-market forecasts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--horizon",
            type=int,
            default=6,
            help="Number of months to forecast.",
        )

    def handle(self, *args, **options):
        horizon = options["horizon"]

        self.stdout.write(
            f"Generating forecasts for the next {horizon} months..."
        )

        engine = LabourForecastEngine()
        run = engine.generate_forecasts(
            horizon=horizon
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Forecast generation completed successfully."
            )
        )

        self.stdout.write(
            f"Run ID: {run.id}"
        )

        self.stdout.write(
            f"Records processed: {run.records_processed}"
        )

        self.stdout.write(
            f"Records created: {run.records_created}"
        )







