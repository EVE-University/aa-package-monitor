from .utils import clean_setting

# Names of additional distribution packages to be monitored
PACKAGE_MONITOR_INCLUDE_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_INCLUDE_PACKAGES", default_value=None, required_type=list
)
