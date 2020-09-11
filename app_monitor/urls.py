from django.urls import path
from . import views


app_name = "app_monitor"

urlpatterns = [
    path("", views.index, name="index"),
    path("app_list_data", views.app_list_data, name="app_list_data"),
    path(
        "update_distributions", views.update_distributions, name="update_distributions"
    ),
]
