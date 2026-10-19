from datetime import date
from random import Random

from django.core.management.base import BaseCommand
from django.db import transaction

from labour.models import (
    State,
    District,
    Sector,
    Occupation,
    OccupationAlias,
    TrainingCentre,
    TrainingCapacity,
    LabourMarketSnapshot,
    DataSource,
)


class Command(BaseCommand):
    help = "Creates realistic pilot labour-market data for SkillTek India."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing demo data before creating new data.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = Random(42)

        if options["clear"]:
            self.stdout.write("Clearing existing demo data...")
            LabourMarketSnapshot.objects.all().delete()
            TrainingCapacity.objects.all().delete()
            TrainingCentre.objects.all().delete()
            OccupationAlias.objects.all().delete()
            Occupation.objects.all().delete()
            Sector.objects.all().delete()
            District.objects.all().delete()
            State.objects.all().delete()
            DataSource.objects.all().delete()

        states_data = {
            "Kerala": {
                "code": "KL",
                "districts": [
                    "Ernakulam",
                    "Thiruvananthapuram",
                    "Kozhikode",
                    "Thrissur",
                ],
            },
            "Karnataka": {
                "code": "KA",
                "districts": [
                    "Bengaluru Urban",
                    "Mysuru",
                    "Mangaluru",
                ],
            },
            "Maharashtra": {
                "code": "MH",
                "districts": [
                    "Mumbai Suburban",
                    "Pune",
                    "Nagpur",
                ],
            },
            "Telangana": {
                "code": "TS",
                "districts": [
                    "Hyderabad",
                    "Warangal",
                ],
            },
        }

        sectors_data = {
            "Information Technology": {
                "code": "IT",
                "occupations": [
                    ("Software Developer", "IT-SD", 4, "growth"),
                    ("Data Analyst", "IT-DA", 4, "growth"),
                    ("Cloud Engineer", "IT-CE", 4, "emerging"),
                    ("Cybersecurity Analyst", "IT-CS", 4, "growth"),
                ],
            },
            "Automotive": {
                "code": "AUTO",
                "occupations": [
                    ("EV Technician", "AUTO-EV", 3, "emerging"),
                    ("Automotive Service Technician", "AUTO-ST", 3, "stable"),
                ],
            },
            "Healthcare": {
                "code": "HC",
                "occupations": [
                    ("Healthcare Assistant", "HC-HA", 3, "growth"),
                    ("Medical Laboratory Technician", "HC-MLT", 3, "stable"),
                ],
            },
            "Renewable Energy": {
                "code": "RE",
                "occupations": [
                    ("Solar PV Technician", "RE-SPV", 3, "emerging"),
                    ("Solar Installation Technician", "RE-SIT", 3, "growth"),
                ],
            },
            "Construction": {
                "code": "CON",
                "occupations": [
                    ("Electrician", "CON-EL", 3, "stable"),
                    ("Construction Technician", "CON-CT", 3, "growth"),
                ],
            },
            "Manufacturing": {
                "code": "MAN",
                "occupations": [
                    ("CNC Machine Operator", "MAN-CNC", 3, "stable"),
                    ("Industrial Maintenance Technician", "MAN-IMT", 3, "declining"),
                ],
            },
            "Logistics": {
                "code": "LOG",
                "occupations": [
                    ("Logistics Coordinator", "LOG-LC", 3, "growth"),
                ],
            },
        }

        self.stdout.write("Creating states and districts...")

        states = {}
        districts = {}

        for state_name, state_info in states_data.items():
            state, _ = State.objects.update_or_create(
                code=state_info["code"],
                defaults={"name": state_name},
            )
            states[state_name] = state

            for district_name in state_info["districts"]:
                district, _ = District.objects.get_or_create(
                    state=state,
                    name=district_name,
                )
                districts[district_name] = district

        self.stdout.write("Creating sectors and occupations...")

        occupations = {}

        for sector_name, sector_info in sectors_data.items():
            sector, _ = Sector.objects.update_or_create(
                code=sector_info["code"],
                defaults={
                    "name": sector_name,
                    "description": f"Pilot labour-market sector: {sector_name}.",
                    "active": True,
                },
            )

            for occupation_name, code, skill_level, scenario in sector_info["occupations"]:
                occupation, _ = Occupation.objects.update_or_create(
                    code=code,
                    defaults={
                        "sector": sector,
                        "name": occupation_name,
                        "description": f"Pilot occupation used for {scenario} demand simulation.",
                        "skill_level": skill_level,
                        "active": True,
                    },
                )

                occupations[code] = {
                    "object": occupation,
                    "scenario": scenario,
                }

                aliases = {
                    "IT-SD": ["Software Engineer", "Software Developer"],
                    "IT-DA": ["Data Analytics", "Data Analyst"],
                    "IT-CE": ["Cloud Engineer", "Cloud Computing Engineer"],
                    "IT-CS": ["Cyber Security Analyst", "Security Analyst"],
                    "AUTO-EV": ["EV Service Technician", "Electric Vehicle Technician"],
                    "AUTO-ST": ["Auto Technician", "Automotive Technician"],
                    "HC-HA": ["Healthcare Worker", "Health Assistant"],
                    "HC-MLT": ["Lab Technician", "Medical Lab Technician"],
                    "RE-SPV": ["Solar PV Technician", "Solar Technician"],
                    "RE-SIT": ["Solar Installer", "Solar Installation Technician"],
                    "CON-EL": ["Electrical Technician", "Electrician"],
                    "CON-CT": ["Construction Worker", "Construction Technician"],
                    "MAN-CNC": ["CNC Operator", "CNC Machine Operator"],
                    "MAN-IMT": ["Maintenance Technician", "Industrial Maintenance Technician"],
                    "LOG-LC": ["Logistics Executive", "Logistics Coordinator"],
                }

                for alias in aliases.get(code, []):
                    OccupationAlias.objects.get_or_create(
                        occupation=occupation,
                        name=alias,
                        defaults={"source": "seed"},
                    )

        self.stdout.write("Creating training centres and capacity...")

        centres = {}

        for district_name, district in districts.items():
            centre_code = f"SKT-{district.id:03d}"

            centre, _ = TrainingCentre.objects.update_or_create(
                centre_code=centre_code,
                defaults={
                    "name": f"Skill Development Centre - {district_name}",
                    "district": district,
                    "active": True,
                },
            )

            centres[district_name] = centre

            for code, occupation_data in occupations.items():
                occupation = occupation_data["object"]

                base_seats = rng.randint(40, 120)

                for year in [2025, 2026]:
                    year_factor = 1.0 if year == 2025 else rng.uniform(1.0, 1.15)

                    seats = max(
                        10,
                        int(base_seats * year_factor),
                    )

                    enrolled = int(seats * rng.uniform(0.65, 0.95))
                    completed = int(enrolled * rng.uniform(0.70, 0.92))

                    TrainingCapacity.objects.update_or_create(
                        training_centre=centre,
                        occupation=occupation,
                        year=year,
                        defaults={
                            "seats": seats,
                            "enrolled": enrolled,
                            "completed": completed,
                        },
                    )

        self.stdout.write("Creating data sources...")

        DataSource.objects.update_or_create(
            name="SkillTek Pilot Dataset",
            defaults={
                "source_type": "demo",
                "description": (
                    "Synthetic pilot dataset designed to simulate "
                    "labour-market demand, worker supply and training signals."
                ),
                "active": True,
            },
        )

        self.stdout.write("Generating 24 months of labour-market history...")

        start_year = 2024
        start_month = 1

        snapshot_count = 0

        for district_name, district in districts.items():
            district_factor = rng.uniform(0.85, 1.20)

            for code, occupation_data in occupations.items():
                occupation = occupation_data["object"]
                scenario = occupation_data["scenario"]

                base_demand = rng.randint(180, 700) * district_factor
                base_supply = rng.randint(150, 650) * district_factor

                for month_index in range(24):
                    year = start_year + (start_month - 1 + month_index) // 12
                    month = (start_month - 1 + month_index) % 12 + 1

                    current_date = date(year, month, 1)

                    if scenario == "growth":
                        demand_multiplier = 1 + (month_index * 0.025)
                        supply_multiplier = 1 + (month_index * 0.012)
                    elif scenario == "emerging":
                        demand_multiplier = 1 + (month_index * 0.045)
                        supply_multiplier = 1 + (month_index * 0.008)
                    elif scenario == "declining":
                        demand_multiplier = max(
                            0.55,
                            1 - (month_index * 0.018),
                        )
                        supply_multiplier = 1 + (month_index * 0.005)
                    else:
                        demand_multiplier = 1 + (
                            month_index * rng.uniform(-0.004, 0.008)
                        )
                        supply_multiplier = 1 + (
                            month_index * rng.uniform(0.001, 0.006)
                        )

                    noise_demand = rng.uniform(0.92, 1.08)
                    noise_supply = rng.uniform(0.94, 1.06)

                    demand = max(
                        1,
                        int(
                            base_demand
                            * demand_multiplier
                            * noise_demand
                        ),
                    )

                    supply = max(
                        1,
                        int(
                            base_supply
                            * supply_multiplier
                            * noise_supply
                        ),
                    )

                    hiring_index = min(
                        100,
                        max(
                            0,
                            round(
                                35
                                + (demand / max(base_demand, 1)) * 35
                                + rng.uniform(-5, 5),
                                2,
                            ),
                        ),
                    )

                    if month_index == 0:
                        growth_rate = 0
                    else:
                        growth_rate = round(
                            ((demand / previous_demand) - 1) * 100,
                            2,
                        )

                    training_seats = rng.randint(35, 130)

                    LabourMarketSnapshot.objects.update_or_create(
                        district=district,
                        occupation=occupation,
                        month=current_date,
                        defaults={
                            "job_demand": demand,
                            "worker_supply": supply,
                            "training_seats": training_seats,
                            "industry_hiring_index": hiring_index,
                            "demand_growth_rate": growth_rate,
                        },
                    )

                    previous_demand = demand
                    snapshot_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Demo dataset created successfully."
        ))
        self.stdout.write(f"States: {State.objects.count()}")
        self.stdout.write(f"Districts: {District.objects.count()}")
        self.stdout.write(f"Sectors: {Sector.objects.count()}")
        self.stdout.write(f"Occupations: {Occupation.objects.count()}")
        self.stdout.write(f"Training centres: {TrainingCentre.objects.count()}")
        self.stdout.write(f"Training records: {TrainingCapacity.objects.count()}")
        self.stdout.write(f"Labour snapshots: {snapshot_count}")





