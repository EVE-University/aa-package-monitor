from app_utils.django import clean_setting

PACKAGE_MONITOR_EXCLUDE_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_EXCLUDE_PACKAGES", default_value=[]
)
"""Names of distribution packages to be excluded."""


PACKAGE_MONITOR_INCLUDE_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_INCLUDE_PACKAGES", default_value=[]
)
"""Names of additional distribution packages to be monitored."""


PACKAGE_MONITOR_NOTIFICATIONS_ENABLED = clean_setting(
    "PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False
)
"""Whether to notify when an update is available
for a currently installed distribution package.
"""

PACKAGE_MONITOR_SHOW_ALL_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True
)
"""Whether to show all distribution packages,
as opposed to only showing packages that contain Django apps.
"""

PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False
)
"""Whether to show distribution packages installed as editable.

Since version information about editable packages is often outdated,
this type of packages are not shown by default.
"""
