from django.urls import path

from . import views

app_name = "package_monitor"

urlpatterns = [
    path("", views.index, name="index"),
    path("package_list_data", views.package_list_data, name="package_list_data"),
    path(
        "refresh_distributions",
        views.refresh_distributions,
        name="refresh_distributions",
    ),
]
