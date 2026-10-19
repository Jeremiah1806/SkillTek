from django.urls import path
from . import views

urlpatterns = [
    path("policy-simulator/", views.policy_simulator, name="policy_simulator"),
    path("alerts/", views.alerts, name="alerts"),
]

