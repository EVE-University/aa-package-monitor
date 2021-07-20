from django.apps import AppConfig

from . import __version__


class PackageMonitorConfig(AppConfig):
    name = "package_monitor"
    label = "package_monitor"
    verbose_name = "Package Monitor v{}".format(__version__)
