from django.apps import AppConfig
from . import __version__


class AppMonitorConfig(AppConfig):
    name = "app_monitor"
    label = "app_monitor"
    verbose_name = "App Monitor v{}".format(__version__)
