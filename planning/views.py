from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from forecasting.models import Forecast
from labour.models import District, Occupation, State
from .models import Alert, PolicySimulation
from .services.simulation_engine import PolicySimulationEngine


@login_required
def policy_simulator(request):
    states = State.objects.prefetch_related("districts").all()
    occupations = Occupation.objects.select_related("sector").all()

    result = None
    selected_state = None
    selected_district = None
    selected_occupation = None
    proposed_seats = ""

    state_id = request.GET.get("state") or request.POST.get("state")
    district_id = request.GET.get("district") or request.POST.get("district")
    occupation_id = request.GET.get("occupation") or request.POST.get("occupation")

    if state_id:
        selected_state = get_object_or_404(State, id=state_id)

    if district_id and selected_state:
        selected_district = get_object_or_404(
            District,
            id=district_id,
            state=selected_state,
        )

    if occupation_id:
        selected_occupation = get_object_or_404(
            Occupation,
            id=occupation_id,
        )

    if request.method == "POST":
        proposed_seats = request.POST.get("proposed_seats", "0")

        try:
            proposed_seats = int(proposed_seats)
        except (TypeError, ValueError):
            proposed_seats = 0

        if selected_state and selected_district and selected_occupation:

            forecast = (
                Forecast.objects
                .filter(
                    run_id=6,
                    district=selected_district,
                    occupation=selected_occupation,
                )
                .order_by("-forecast_month")
                .first()
            )

            if forecast:
                engine = PolicySimulationEngine()

                result = engine.simulate(
                    district=selected_district,
                    occupation=selected_occupation,
                    forecast=forecast,
                    proposed_training_seats=proposed_seats,
                    user=request.user,
                    save=True,
                )

    recent_simulations = (
        PolicySimulation.objects
        .select_related(
            "district",
            "district__state",
            "occupation",
        )
        .filter(created_by=request.user)
        .order_by("-created_at")[:10]
    )

    context = {
        "states": states,
        "occupations": occupations,
        "result": result,
        "selected_state": selected_state,
        "selected_district": selected_district,
        "selected_occupation": selected_occupation,
        "proposed_seats": proposed_seats,
        "recent_simulations": recent_simulations,
    }

    return render(
        request,
        "planning/policy_simulator.html",
        context,
    )


@login_required
def alerts(request):
    base_alerts = (
        Alert.objects
        .select_related(
            "district",
            "district__state",
            "occupation",
            "occupation__sector",
            "forecast",
            "forecast__skill_gap",
        )
        .filter(forecast__run_id=6)
        .order_by(
            "district_id",
            "occupation_id",
            "alert_type",
            "-forecast__forecast_month",
            "-created_at",
        )
    )

    severity = request.GET.get("severity", "").strip()
    alert_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "active").strip()
    search = request.GET.get("search", "").strip()

    filtered_alerts = base_alerts

    if severity:
        filtered_alerts = filtered_alerts.filter(
            severity=severity
        )

    if alert_type:
        filtered_alerts = filtered_alerts.filter(
            alert_type=alert_type
        )

    if status == "resolved":
        filtered_alerts = filtered_alerts.filter(
            is_resolved=True
        )
    elif status != "all":
        filtered_alerts = filtered_alerts.filter(
            is_resolved=False
        )

    if search:
        filtered_alerts = filtered_alerts.filter(
            Q(district__name__icontains=search)
            | Q(occupation__name__icontains=search)
            | Q(title__icontains=search)
            | Q(message__icontains=search)
        )

    unique_alerts = {}

    for alert in filtered_alerts:
        key = (
            alert.district_id,
            alert.occupation_id,
            alert.alert_type,
        )

        if key not in unique_alerts:
            unique_alerts[key] = alert

    alerts_list = list(unique_alerts.values())

    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    alerts_list.sort(
        key=lambda alert: (
            severity_order.get(alert.severity, 9),
            -(alert.forecast.skill_gap.risk_score or 0),
        )
    )

    for alert in alerts_list:
        occupation_name = alert.occupation.name
        district_name = alert.district.name

        if alert.alert_type == "shortage":
            alert.title = (
                f"Labour shortage: {occupation_name} in {district_name}"
            )

        elif alert.alert_type == "oversupply":
            alert.title = (
                f"Potential oversupply: {occupation_name} in {district_name}"
            )

        elif alert.alert_type == "emerging":
            alert.title = (
                f"Emerging skill signal: {occupation_name} in {district_name}"
            )

        elif alert.alert_type == "rapid_growth":
            alert.title = (
                f"Rapid demand growth: {occupation_name} in {district_name}"
            )

    top_alerts = alerts_list[:20]

    active_alerts = (
        Alert.objects
        .select_related(
            "district",
            "occupation",
            "forecast",
            "forecast__skill_gap",
        )
        .filter(
            forecast__run_id=6,
            is_resolved=False,
        )
        .order_by(
            "district_id",
            "occupation_id",
            "alert_type",
            "-forecast__forecast_month",
        )
    )

    unique_active = {}

    for alert in active_alerts:
        key = (
            alert.district_id,
            alert.occupation_id,
            alert.alert_type,
        )

        if key not in unique_active:
            unique_active[key] = alert

    unique_active_alerts = list(unique_active.values())

    context = {
        "alerts": top_alerts,
        "total_alerts": len(unique_active_alerts),
        "critical_count": sum(
            1
            for alert in unique_active_alerts
            if alert.severity == "critical"
        ),
        "high_count": sum(
            1
            for alert in unique_active_alerts
            if alert.severity == "high"
        ),
        "shortage_count": sum(
            1
            for alert in unique_active_alerts
            if alert.alert_type == "shortage"
        ),
        "oversupply_count": sum(
            1
            for alert in unique_active_alerts
            if alert.alert_type == "oversupply"
        ),
        "emerging_count": sum(
            1
            for alert in unique_active_alerts
            if alert.alert_type == "emerging"
        ),
        "rapid_growth_count": sum(
            1
            for alert in unique_active_alerts
            if alert.alert_type == "rapid_growth"
        ),
        "selected_severity": severity,
        "selected_type": alert_type,
        "selected_status": status,
        "search_query": search,
        "showing_count": len(top_alerts),
    }

    return render(
        request,
        "planning/alerts.html",
        context,
    )







