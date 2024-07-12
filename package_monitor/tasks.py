"""Tasks for Package Monitor."""

from celery import chain, shared_task

from django.core.cache import cache
from django.utils.timezone import now

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_NOTIFICATIONS_ENABLED,
    PACKAGE_MONITOR_NOTIFICATIONS_MAX_DELAY,
    PACKAGE_MONITOR_NOTIFICATIONS_REPEAT,
    PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE,
    PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
)
from .core import schedule
from .models import Distribution

logger = LoggerAddTag(get_extension_logger(__name__), __title__)
CACHE_KEY_LAST_REPORT = "package-monitor-notification-last-report"


@shared_task(time_limit=3600)
def update_distributions():
    """Run regular tasks."""
    if _should_send_notifications():
        chain(update_all_distributions.si(), send_update_notification.si()).delay()
    else:
        update_all_distributions.delay()


def _should_send_notifications() -> bool:
    if not PACKAGE_MONITOR_NOTIFICATIONS_ENABLED:
        return False
    last_report = cache.get(key=CACHE_KEY_LAST_REPORT)
    is_due = schedule.is_notification_due(
        schedule_text=PACKAGE_MONITOR_NOTIFICATIONS_SCHEDULE,
        max_delay=PACKAGE_MONITOR_NOTIFICATIONS_MAX_DELAY,
        last_report=last_report,
    )
    if not is_due:
        return False
    return True


@shared_task
def update_all_distributions():
    """Update all distributions."""
    Distribution.objects.update_all()


@shared_task
def send_update_notification(should_repeat: bool = False):
    """Send update notification to inform about new versions."""
    Distribution.objects.send_update_notification(
        show_editable=PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
        should_repeat=should_repeat or PACKAGE_MONITOR_NOTIFICATIONS_REPEAT,
    )
    cache.set(key=CACHE_KEY_LAST_REPORT, value=now(), timeout=None)
