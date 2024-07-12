"""Settings for Package Monitor."""

from app_utils.app_settings import clean_setting

PACKAGE_MONITOR_CUSTOM_REQUIREMENTS = clean_setting(
    "PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", default_value=[]
)
"""List of custom requirements that all potential updates are checked against.
Example: ["gunicorn<20"]
"""

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

PACKAGE_MONITOR_NOTIFICATIONS_REPEAT = clean_setting(
    "PACKAGE_MONITOR_NOTIFICATIONS_REPEAT", False
)
"""Whether to repeat notifying about the same updates."""

PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE = clean_setting(
    "PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE", ""
)
"""When to send notifications about updates.
If not set, update notifications can be send every time the regular task runs.

The schedule can be defined in natural language. Examples: "every day at 10:00",
"every saturday at 18:00", "every first saturday every month at 15:00".
For more information about the syntax please see: [recurrent package](https://github.com/kvh/recurrent)
"""

PACKAGE_MONITOR_NOTIFICATIONS_MAX_DELAY = clean_setting(
    "PACKAGE_MONITOR_NOTIFICATIONS_MAX_DELAY", 5400
)
"""Maximum delay in seconds between the scheduled event for firing a notification
and the time the notification is issued.

This value should be synchronized with the timing of the recurring task.
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


PACKAGE_MONITOR_PROTECTED_PACKAGES = clean_setting(
    "PACKAGE_MONITOR_PROTECTED_PACKAGES", ["allianceauth", "django"]
)
"""Names of protected packages.

Updates can include requirements for updating other packages,
which can potentially break the current AA installation.

For example: You have Django 4.2 installed
and an update to a package requires Django 5 or higher.
Then installing that package may break your installation.

When enabled Package Monitor will not show updates,
which would cause an indirect update of a protected package.

And empty list disables this feature.
"""
