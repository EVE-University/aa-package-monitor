from app_utils.django import clean_setting

# Names of additional distribution packages to be monitored
PACKAGE_MONITOR_INCLUDE_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_INCLUDE_PACKAGES", default_value=None, required_type=list
)

# Whether to show all distribution packages, as opposed to only showing packages
# that contain Django apps
PACKAGE_MONITOR_SHOW_ALL_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False
)
