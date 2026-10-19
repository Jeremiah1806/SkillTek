from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
import json
from django.db.models import Avg, Max, Min

from forecasting.models import Forecast, SkillGap
from labour.models import District, LabourMarketSnapshot, Occupation, State
from planning.models import Alert, Recommendation

from .forms import ProfileForm, RegisterForm
from .models import UserProfile


def home(request):
    return render(request, "core/home.html")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            login(request, user)
            return redirect("profile")
    else:
        form = RegisterForm()

    return render(request, "auth/register.html", {"form": form})


@login_required
def dashboard(request):
    forecasts = Forecast.objects.select_related(
        "district",
        "district__state",
        "occupation",
        "occupation__sector",
        "run",
    ).filter(
        run__id=6
    ).order_by(
        "district__state__name",
        "district__name",
        "occupation__name",
        "forecast_month",
    )

    skill_gaps = SkillGap.objects.filter(
        forecast__run_id=6
    )

    total_states = State.objects.count()
    total_districts = District.objects.count()
    total_occupations = Occupation.objects.count()
    total_forecasts = forecasts.count()
    states = State.objects.prefetch_related("districts").all()

    critical_shortages = skill_gaps.filter(
        severity="critical_shortage"
    ).count()

    shortages = skill_gaps.filter(
        severity="shortage"
    ).count()

    critical_oversupply = skill_gaps.filter(
        severity="critical_oversupply"
    ).count()

    oversupply = skill_gaps.filter(
        severity="oversupply"
    ).count()

    # ---------------------------------------------------------
    # Aggregate each district + occupation across the forecast
    # horizon instead of showing every forecast month separately.
    # ---------------------------------------------------------

    groups = {}

    for forecast in forecasts:
        key = (
            forecast.district_id,
            forecast.occupation_id,
        )

        if key not in groups:
            groups[key] = {
                "district": forecast.district,
                "occupation": forecast.occupation,
                "forecasts": [],
                "gaps": [],
            }

        groups[key]["forecasts"].append(forecast)

        try:
            groups[key]["gaps"].append(
                forecast.skill_gap
            )
        except SkillGap.DoesNotExist:
            pass

    aggregated_skills = []

    for group in groups.values():
        forecast_items = group["forecasts"]
        gap_items = group["gaps"]

        if not forecast_items:
            continue

        first_forecast = forecast_items[0]
        last_forecast = forecast_items[-1]

        first_gap = (
            gap_items[0].gap_value
            if gap_items
            else 0
        )

        last_gap = (
            gap_items[-1].gap_value
            if gap_items
            else 0
        )

        average_risk = (
            sum(item.risk_score for item in gap_items)
            / len(gap_items)
            if gap_items
            else 0
        )

        maximum_risk = (
            max(item.risk_score for item in gap_items)
            if gap_items
            else 0
        )

        # Determine the dominant severity across the horizon.
        severity_counts = {}

        for item in gap_items:
            severity_counts[item.severity] = (
                severity_counts.get(item.severity, 0) + 1
            )

        dominant_severity = (
            max(
                severity_counts,
                key=severity_counts.get,
            )
            if severity_counts
            else "balanced"
        )

        if last_gap > first_gap:
            trend = "worsening"
        elif last_gap < first_gap:
            trend = "improving"
        else:
            trend = "stable"

        aggregated_skills.append({
            "district": group["district"],
            "occupation": group["occupation"],
            "first_gap": first_gap,
            "last_gap": last_gap,
            "average_risk": round(
                average_risk,
                1,
            ),
            "maximum_risk": round(
                maximum_risk,
                1,
            ),
            "severity": dominant_severity,
            "trend": trend,
            "start_month": first_forecast.forecast_month,
            "end_month": last_forecast.forecast_month,
            "forecasts": forecast_items,
        })

    # Highest-risk district/occupation combinations.
    highest_risk = sorted(
        aggregated_skills,
        key=lambda item: item["maximum_risk"],
        reverse=True,
    )[:8]

    # ---------------------------------------------------------
    # Aggregate planner recommendations by district + occupation
    # ---------------------------------------------------------

    recommendations = Recommendation.objects.select_related(
        "district",
        "occupation",
        "alert",
        "alert__forecast",
    ).filter(
        alert__forecast__run_id=6
    ).order_by(
        "-created_at"
    )

    recommendation_groups = {}

    for recommendation in recommendations:
        key = (
            recommendation.district_id,
            recommendation.occupation_id,
        )

        if key not in recommendation_groups:
            recommendation_groups[key] = {
                "district": recommendation.district,
                "occupation": recommendation.occupation,
                "items": [],
            }

        recommendation_groups[key]["items"].append(
            recommendation
        )

    aggregated_recommendations = []

    for group in recommendation_groups.values():
        items = group["items"]

        if not items:
            continue

        highest_priority = items[0]

        for item in items:
            priority_rank = {
                "critical": 4,
                "high": 3,
                "medium": 2,
                "low": 1,
            }

            if priority_rank.get(
                item.priority,
                0,
            ) > priority_rank.get(
                highest_priority.priority,
                0,
            ):
                highest_priority = item

        suggested_seats = max(
            item.suggested_seats
            for item in items
        )

        aggregated_recommendations.append({
            "district": group["district"],
            "occupation": group["occupation"],
            "recommendation_type": highest_priority.recommendation_type,
            "title": highest_priority.title,
            "explanation": highest_priority.explanation,
            "priority": highest_priority.priority,
            "suggested_seats": suggested_seats,
        })

    priority_rank = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    aggregated_recommendations.sort(
        key=lambda item: priority_rank.get(
            item["priority"],
            0,
        ),
        reverse=True,
    )

    top_recommendations = aggregated_recommendations[:6]

    # ---------------------------------------------------------
    # Aggregate alerts by district + occupation.
    # ---------------------------------------------------------

    alerts = Alert.objects.select_related(
        "district",
        "district__state",
        "occupation",
        "forecast",
    ).filter(
        forecast__run_id=6,
        is_resolved=False,
    )

    alert_groups = {}

    for alert in alerts:
        key = (
            alert.district_id,
            alert.occupation_id,
            alert.alert_type,
        )

        if key not in alert_groups:
            alert_groups[key] = {
                "district": alert.district,
                "occupation": alert.occupation,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "count": 0,
                "latest": alert,
            }

        alert_groups[key]["count"] += 1

        severity_rank = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }

        if severity_rank.get(
            alert.severity,
            0,
        ) > severity_rank.get(
            alert_groups[key]["severity"],
            0,
        ):
            alert_groups[key]["severity"] = alert.severity

        if alert.forecast.forecast_month > alert_groups[key][
            "latest"
        ].forecast.forecast_month:
            alert_groups[key]["latest"] = alert

    aggregated_alerts = list(
        alert_groups.values()
    )

    aggregated_alerts.sort(
        key=lambda item: (
            {
                "critical": 4,
                "high": 3,
                "medium": 2,
                "low": 1,
            }.get(item["severity"], 0),
            item["latest"].forecast.forecast_month,
        ),
        reverse=True,
    )

    recent_alerts = aggregated_alerts[:8]

    # ---------------------------------------------------------
    # Overall Skill Health Score
    # ---------------------------------------------------------

    total_groups = len(aggregated_skills)

    balanced_groups = sum(
        1
        for item in aggregated_skills
        if item["severity"] == "balanced"
    )

    if total_groups:
        balance_score = (
            balanced_groups / total_groups
        ) * 100
    else:
        balance_score = 0

    average_risk = (
        sum(
            item["average_risk"]
            for item in aggregated_skills
        ) / total_groups
        if total_groups
        else 0
    )

    skill_health_score = round(
        max(
            0,
            min(
                100,
                (balance_score * 0.4)
                + ((100 - average_risk) * 0.6),
            ),
        )
    )

    latest_forecast = forecasts.order_by(
        "-forecast_month"
    ).first()

    context = {
        "total_states": total_states,
        "states": states,
        "total_districts": total_districts,
        "total_occupations": total_occupations,
        "total_forecasts": total_forecasts,

        "critical_shortages": critical_shortages,
        "shortages": shortages,
        "critical_oversupply": critical_oversupply,
        "oversupply": oversupply,

        "active_alerts": alerts.count(),

        "skill_health_score": skill_health_score,

        "highest_risk": highest_risk,

        "top_recommendations": top_recommendations,

        "recent_alerts": recent_alerts,

        "latest_forecast": latest_forecast,

        "forecast_groups": aggregated_skills,
    }

    return render(
        request,
        "core/dashboard.html",
        context,
    )


@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":
        form = ProfileForm(
            request.POST,
            instance=user_profile,
        )

        if form.is_valid():
            profile_data = form.save(commit=False)
            profile_data.profile_completed = True
            profile_data.save()

            messages.success(
                request,
                "Profile updated successfully.",
            )

            return redirect("dashboard")
    else:
        form = ProfileForm(instance=user_profile)

    return render(
        request,
        "core/profile.html",
        {"form": form},
    )


@login_required
def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def district_detail(request, district_id):
    district = District.objects.select_related(
        "state"
    ).get(
        id=district_id
    )

    forecasts = Forecast.objects.select_related(
        "occupation",
        "occupation__sector",
    ).filter(
        run_id=6,
        district=district,
    ).order_by(
        "occupation__name",
        "forecast_month",
    )

    skill_gaps = SkillGap.objects.select_related(
        "forecast",
    ).filter(
        forecast__run_id=6,
        forecast__district=district,
    )

    grouped = {}

    for forecast in forecasts:
        key = forecast.occupation_id

        if key not in grouped:
            grouped[key] = {
                "occupation": forecast.occupation,
                "forecasts": [],
                "gaps": [],
            }

        grouped[key]["forecasts"].append(forecast)

        try:
            grouped[key]["gaps"].append(
                forecast.skill_gap
            )
        except SkillGap.DoesNotExist:
            pass

    shortage_markets = []
    oversupply_markets = []
    forecast_json = {}

    for group in grouped.values():
        gaps = group["gaps"]

        if not gaps:
            continue

        latest_gap = gaps[-1]

        item = {
            "occupation": group["occupation"],
            "latest_gap": latest_gap.gap_value,
            "risk": max(
                gap.risk_score
                for gap in gaps
            ),
            "severity": latest_gap.severity,
            "forecasts": group["forecasts"],
        }

        occupation_id = str(
            group["occupation"].id
        )

        forecast_json[occupation_id] = {
            "name": group["occupation"].name,
            "labels": [
                forecast.forecast_month.strftime("%b %Y")
                for forecast in group["forecasts"]
            ],
            "demand": [
                round(forecast.predicted_demand)
                for forecast in group["forecasts"]
            ],
            "supply": [
                round(forecast.predicted_supply)
                for forecast in group["forecasts"]
            ],
        }

        if latest_gap.gap_value > 0:
            shortage_markets.append(item)
        elif latest_gap.gap_value < 0:
            oversupply_markets.append(item)

    shortage_markets.sort(
        key=lambda item: item["latest_gap"],
        reverse=True,
    )

    oversupply_markets.sort(
        key=lambda item: item["latest_gap"],
    )

    # Aggregate recommendations by occupation.
    recommendation_queryset = Recommendation.objects.select_related(
        "occupation",
        "alert",
        "alert__forecast",
    ).filter(
        district=district,
        alert__forecast__run_id=6,
    ).order_by(
        "-created_at"
    )

    recommendation_groups = {}

    for recommendation in recommendation_queryset:
        key = recommendation.occupation_id

        if key not in recommendation_groups:
            recommendation_groups[key] = {
                "occupation": recommendation.occupation,
                "title": recommendation.title,
                "explanation": recommendation.explanation,
                "priority": recommendation.priority,
                "recommendation_type": recommendation.recommendation_type,
                "suggested_seats": recommendation.suggested_seats,
                "count": 0,
            }

        group = recommendation_groups[key]

        group["count"] += 1

        priority_rank = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }

        if priority_rank.get(
            recommendation.priority,
            0,
        ) > priority_rank.get(
            group["priority"],
            0,
        ):
            group["priority"] = recommendation.priority
            group["title"] = recommendation.title
            group["explanation"] = recommendation.explanation
            group["recommendation_type"] = recommendation.recommendation_type

        group["suggested_seats"] = max(
            group["suggested_seats"],
            recommendation.suggested_seats,
        )

    recommendations = list(
        recommendation_groups.values()
    )

    recommendations.sort(
        key=lambda item: (
            {
                "critical": 4,
                "high": 3,
                "medium": 2,
                "low": 1,
            }.get(item["priority"], 0),
            item["suggested_seats"],
        ),
        reverse=True,
    )

    first_occupation_id = None

    if forecast_json:
        first_occupation_id = next(
            iter(forecast_json)
        )

    context = {
        "district": district,
        "forecasts": forecasts,
        "skill_gaps": skill_gaps,
        "shortage_markets": shortage_markets[:8],
        "oversupply_markets": oversupply_markets[:8],
        "recommendations": recommendations[:8],
        "forecast_json": json.dumps(forecast_json),
        "total_markets": len(grouped),
        "first_occupation_id": first_occupation_id,
    }

    return render(
        request,
        "core/district_detail.html",
        context,
    )


@login_required
def state_detail(request, state_id):
    state = State.objects.get(id=state_id)

    forecasts = Forecast.objects.select_related(
        "district",
        "district__state",
        "occupation",
        "occupation__sector",
    ).filter(
        run_id=6,
        district__state=state,
    ).order_by(
        "district__name",
        "occupation__name",
        "forecast_month",
    )

    skill_gaps = SkillGap.objects.select_related(
        "forecast",
    ).filter(
        forecast__run_id=6,
        forecast__district__state=state,
    )

    # ---------------------------------------------------------
    # Aggregate each district + occupation across six months.
    # ---------------------------------------------------------

    groups = {}

    for forecast in forecasts:
        key = (
            forecast.district_id,
            forecast.occupation_id,
        )

        if key not in groups:
            groups[key] = {
                "district": forecast.district,
                "occupation": forecast.occupation,
                "forecasts": [],
                "gaps": [],
            }

        groups[key]["forecasts"].append(forecast)

        try:
            groups[key]["gaps"].append(
                forecast.skill_gap
            )
        except SkillGap.DoesNotExist:
            pass

    markets = []

    for group in groups.values():
        gaps = group["gaps"]

        if not gaps:
            continue

        first_gap = gaps[0].gap_value
        last_gap = gaps[-1].gap_value

        average_risk = (
            sum(gap.risk_score for gap in gaps)
            / len(gaps)
        )

        maximum_risk = max(
            gap.risk_score
            for gap in gaps
        )

        severity_counts = {}

        for gap in gaps:
            severity_counts[gap.severity] = (
                severity_counts.get(
                    gap.severity,
                    0,
                ) + 1
            )

        dominant_severity = (
            max(
                severity_counts,
                key=severity_counts.get,
            )
            if severity_counts
            else "balanced"
        )

        if last_gap > first_gap:
            trend = "worsening"
        elif last_gap < first_gap:
            trend = "improving"
        else:
            trend = "stable"

        markets.append({
            "district": group["district"],
            "occupation": group["occupation"],
            "first_gap": first_gap,
            "last_gap": last_gap,
            "average_risk": round(
                average_risk,
                1,
            ),
            "maximum_risk": round(
                maximum_risk,
                1,
            ),
            "severity": dominant_severity,
            "trend": trend,
            "forecasts": group["forecasts"],
        })

    # ---------------------------------------------------------
    # State-level counts.
    # ---------------------------------------------------------

    shortage_markets = [
        market
        for market in markets
        if market["last_gap"] > 0
    ]

    oversupply_markets = [
        market
        for market in markets
        if market["last_gap"] < 0
    ]

    critical_shortages = sum(
        1
        for market in markets
        if market["severity"] == "critical_shortage"
    )

    critical_oversupply = sum(
        1
        for market in markets
        if market["severity"] == "critical_oversupply"
    )

    balanced_markets = sum(
        1
        for market in markets
        if market["severity"] == "balanced"
    )

    total_markets = len(markets)

    average_risk = (
        sum(
            market["average_risk"]
            for market in markets
        ) / total_markets
        if total_markets
        else 0
    )

    balance_score = (
        balanced_markets / total_markets * 100
        if total_markets
        else 0
    )

    skill_health_score = round(
        max(
            0,
            min(
                100,
                (balance_score * 0.4)
                + ((100 - average_risk) * 0.6),
            ),
        )
    )

    # ---------------------------------------------------------
    # Highest-risk markets.
    # ---------------------------------------------------------

    highest_risk = sorted(
        markets,
        key=lambda item: item["maximum_risk"],
        reverse=True,
    )[:10]

    # ---------------------------------------------------------
    # District summary.
    # ---------------------------------------------------------

    district_groups = {}

    for market in markets:
        district_id = market["district"].id

        if district_id not in district_groups:
            district_groups[district_id] = {
                "district": market["district"],
                "markets": [],
            }

        district_groups[district_id]["markets"].append(
            market
        )

    district_summary = []

    for group in district_groups.values():
        district_markets = group["markets"]

        shortage_count = sum(
            1
            for market in district_markets
            if market["last_gap"] > 0
        )

        oversupply_count = sum(
            1
            for market in district_markets
            if market["last_gap"] < 0
        )

        district_risk = max(
            market["maximum_risk"]
            for market in district_markets
        )

        district_summary.append({
            "district": group["district"],
            "markets": len(district_markets),
            "shortages": shortage_count,
            "oversupply": oversupply_count,
            "maximum_risk": round(
                district_risk,
                1,
            ),
        })

    district_summary.sort(
        key=lambda item: item["maximum_risk"],
        reverse=True,
    )

    # ---------------------------------------------------------
    # Recommendations for this state.
    # ---------------------------------------------------------

    recommendations = Recommendation.objects.select_related(
        "district",
        "occupation",
        "alert",
        "alert__forecast",
    ).filter(
        district__state=state,
        alert__forecast__run_id=6,
    )

    recommendation_groups = {}

    for recommendation in recommendations:
        key = (
            recommendation.district_id,
            recommendation.occupation_id,
        )

        if key not in recommendation_groups:
            recommendation_groups[key] = {
                "district": recommendation.district,
                "occupation": recommendation.occupation,
                "items": [],
            }

        recommendation_groups[key]["items"].append(
            recommendation
        )

    priority_rank = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    aggregated_recommendations = []

    for group in recommendation_groups.values():
        items = group["items"]

        if not items:
            continue

        best = max(
            items,
            key=lambda item: priority_rank.get(
                item.priority,
                0,
            ),
        )

        aggregated_recommendations.append({
            "district": group["district"],
            "occupation": group["occupation"],
            "title": best.title,
            "explanation": best.explanation,
            "priority": best.priority,
            "recommendation_type": best.recommendation_type,
            "suggested_seats": max(
                item.suggested_seats
                for item in items
            ),
            "count": len(items),
        })

    aggregated_recommendations.sort(
        key=lambda item: (
            priority_rank.get(
                item["priority"],
                0,
            ),
            item["suggested_seats"],
        ),
        reverse=True,
    )

    top_recommendations = (
        aggregated_recommendations[:8]
    )

    latest_forecast = forecasts.order_by(
        "-forecast_month"
    ).first()

    context = {
        "state": state,
        "total_districts": len(
            district_summary
        ),
        "total_markets": total_markets,
        "shortage_markets": len(
            shortage_markets
        ),
        "oversupply_markets": len(
            oversupply_markets
        ),
        "critical_shortages": critical_shortages,
        "critical_oversupply": critical_oversupply,
        "skill_health_score": skill_health_score,
        "average_risk": round(
            average_risk,
            1,
        ),
        "highest_risk": highest_risk,
        "district_summary": district_summary,
        "top_recommendations": top_recommendations,
        "latest_forecast": latest_forecast,
    }

    return render(
        request,
        "core/state_detail.html",
        context,
    )


@login_required
def occupation_detail(request, occupation_id):
    occupation = Occupation.objects.select_related(
        "sector"
    ).get(
        id=occupation_id
    )

    forecasts = Forecast.objects.select_related(
        "district",
        "district__state",
        "occupation",
        "occupation__sector",
    ).filter(
        run_id=6,
        occupation=occupation,
    ).order_by(
        "district__state__name",
        "district__name",
        "forecast_month",
    )

    skill_gaps = SkillGap.objects.select_related(
        "forecast",
    ).filter(
        forecast__run_id=6,
        forecast__occupation=occupation,
    )

    # ---------------------------------------------------------
    # Aggregate each district across the forecast horizon.
    # ---------------------------------------------------------

    district_groups = {}

    for forecast in forecasts:
        district_id = forecast.district_id

        if district_id not in district_groups:
            district_groups[district_id] = {
                "district": forecast.district,
                "forecasts": [],
                "gaps": [],
            }

        district_groups[district_id]["forecasts"].append(
            forecast
        )

        try:
            district_groups[district_id]["gaps"].append(
                forecast.skill_gap
            )
        except SkillGap.DoesNotExist:
            pass

    markets = []

    for group in district_groups.values():
        gaps = group["gaps"]

        if not gaps:
            continue

        first_gap = gaps[0].gap_value
        last_gap = gaps[-1].gap_value

        average_risk = (
            sum(
                gap.risk_score
                for gap in gaps
            ) / len(gaps)
        )

        maximum_risk = max(
            gap.risk_score
            for gap in gaps
        )

        severity_counts = {}

        for gap in gaps:
            severity_counts[gap.severity] = (
                severity_counts.get(
                    gap.severity,
                    0,
                ) + 1
            )

        dominant_severity = (
            max(
                severity_counts,
                key=severity_counts.get,
            )
            if severity_counts
            else "balanced"
        )

        if last_gap > first_gap:
            trend = "worsening"
        elif last_gap < first_gap:
            trend = "improving"
        else:
            trend = "stable"

        markets.append({
            "district": group["district"],
            "forecasts": group["forecasts"],
            "gaps": gaps,
            "first_gap": first_gap,
            "last_gap": last_gap,
            "average_risk": round(
                average_risk,
                1,
            ),
            "maximum_risk": round(
                maximum_risk,
                1,
            ),
            "severity": dominant_severity,
            "trend": trend,
        })

    # ---------------------------------------------------------
    # Overall occupation-level demand and supply.
    # ---------------------------------------------------------

    total_current_demand = 0
    total_current_supply = 0
    total_projected_demand = 0
    total_projected_supply = 0

    for market in markets:
        market_forecasts = market["forecasts"]

        if not market_forecasts:
            continue

        current = market_forecasts[0]
        projected = market_forecasts[-1]

        total_current_demand += current.predicted_demand
        total_current_supply += current.predicted_supply
        total_projected_demand += projected.predicted_demand
        total_projected_supply += projected.predicted_supply

    current_gap = (
        total_current_demand
        - total_current_supply
    )

    projected_gap = (
        total_projected_demand
        - total_projected_supply
    )

    # ---------------------------------------------------------
    # National occupation forecast.
    # Aggregate demand and supply across districts by month.
    # ---------------------------------------------------------

    monthly_data = {}

    for forecast in forecasts:
        month_key = forecast.forecast_month

        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "demand": 0,
                "supply": 0,
            }

        monthly_data[month_key]["demand"] += (
            forecast.predicted_demand
        )

        monthly_data[month_key]["supply"] += (
            forecast.predicted_supply
        )

    monthly_data = dict(
        sorted(
            monthly_data.items()
        )
    )

    forecast_labels = [
        month.strftime("%b %Y")
        for month in monthly_data
    ]

    forecast_demand = [
        round(data["demand"])
        for data in monthly_data.values()
    ]

    forecast_supply = [
        round(data["supply"])
        for data in monthly_data.values()
    ]

    forecast_json = json.dumps({
        "labels": forecast_labels,
        "demand": forecast_demand,
        "supply": forecast_supply,
    })

    # ---------------------------------------------------------
    # Risk and market counts.
    # ---------------------------------------------------------

    shortage_markets = sum(
        1
        for market in markets
        if market["last_gap"] > 0
    )

    oversupply_markets = sum(
        1
        for market in markets
        if market["last_gap"] < 0
    )

    critical_shortages = sum(
        1
        for market in markets
        if market["severity"] == "critical_shortage"
    )

    critical_oversupply = sum(
        1
        for market in markets
        if market["severity"] == "critical_oversupply"
    )

    average_risk = (
        sum(
            market["average_risk"]
            for market in markets
        ) / len(markets)
        if markets
        else 0
    )

    # ---------------------------------------------------------
    # Recommendations.
    # ---------------------------------------------------------

    recommendations = Recommendation.objects.select_related(
        "district",
        "district__state",
        "occupation",
        "alert",
        "alert__forecast",
    ).filter(
        occupation=occupation,
        alert__forecast__run_id=6,
    )

    recommendation_groups = {}

    for recommendation in recommendations:
        key = (
            recommendation.district_id,
            recommendation.occupation_id,
        )

        if key not in recommendation_groups:
            recommendation_groups[key] = {
                "district": recommendation.district,
                "items": [],
            }

        recommendation_groups[key]["items"].append(
            recommendation
        )

    priority_rank = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    aggregated_recommendations = []

    for group in recommendation_groups.values():
        items = group["items"]

        if not items:
            continue

        best = max(
            items,
            key=lambda item: priority_rank.get(
                item.priority,
                0,
            ),
        )

        aggregated_recommendations.append({
            "district": group["district"],
            "title": best.title,
            "explanation": best.explanation,
            "priority": best.priority,
            "recommendation_type": best.recommendation_type,
            "suggested_seats": max(
                item.suggested_seats
                for item in items
            ),
        })

    aggregated_recommendations.sort(
        key=lambda item: (
            priority_rank.get(
                item["priority"],
                0,
            ),
            item["suggested_seats"],
        ),
        reverse=True,
    )

    latest_forecast = forecasts.order_by(
        "-forecast_month"
    ).first()

    context = {
        "occupation": occupation,
        "markets": markets,
        "total_districts": len(markets),
        "shortage_markets": shortage_markets,
        "oversupply_markets": oversupply_markets,
        "critical_shortages": critical_shortages,
        "critical_oversupply": critical_oversupply,
        "average_risk": round(
            average_risk,
            1,
        ),
        "current_demand": round(
            total_current_demand
        ),
        "current_supply": round(
            total_current_supply
        ),
        "projected_demand": round(
            total_projected_demand
        ),
        "projected_supply": round(
            total_projected_supply
        ),
        "current_gap": round(
            current_gap
        ),
        "projected_gap": round(
            projected_gap
        ),
        "forecast_json": forecast_json,
        "highest_risk": sorted(
            markets,
            key=lambda item: item["maximum_risk"],
            reverse=True,
        )[:10],
        "recommendations": aggregated_recommendations[:8],
        "latest_forecast": latest_forecast,
    }

    return render(
        request,
        "core/occupation_detail.html",
        context,
    )



