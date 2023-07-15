"""Django app config for Package Monitor."""

from django.apps import AppConfig

from . import __version__


class PackageMonitorConfig(AppConfig):
    name = "package_monitor"
    label = "package_monitor"
    verbose_name = f"Package Monitor v{__version__}"
