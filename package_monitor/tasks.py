"""Tasks for Package Monitor."""

from celery import chain, shared_task

from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_NOTIFICATIONS_ENABLED,
    PACKAGE_MONITOR_NOTIFICATIONS_REPEAT,
    PACKAGE_MONITOR_NOTIFICATIONS_TIMEOUT,
    PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
)
from .models import Distribution

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


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
    timeout_hours = PACKAGE_MONITOR_NOTIFICATIONS_TIMEOUT
    if max(timeout_hours, 0) == 0:
        return True
    key = "package-monitor-notification-timeout"
    if cache.get(key):
        return False
    cache.set(key=key, value=True, timeout=timeout_hours * 3600)
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
