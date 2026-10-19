from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register_view, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("district/<int:district_id>/", views.district_detail, name="district_detail"),
    path("state/<int:state_id>/", views.state_detail, name="state_detail"),
    path("occupation/<int:occupation_id>/", views.occupation_detail, name="occupation_detail"),
]