from django.urls import path
from . import views


app_name = "package_monitor"

urlpatterns = [
    path("", views.index, name="index"),
    path("package_list_data", views.package_list_data, name="package_list_data"),
    path(
        "update_distributions", views.update_distributions, name="update_distributions"
    ),
]
