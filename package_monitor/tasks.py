"""Tasks for Package Monitor."""

from celery import chain, shared_task

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_NOTIFICATIONS_ENABLED,
    PACKAGE_MONITOR_REPEAT_NOTIFICATIONS,
    PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
)
from .models import Distribution

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@shared_task(time_limit=3600)
def update_distributions():
    """Run regular tasks."""
    if PACKAGE_MONITOR_NOTIFICATIONS_ENABLED:
        chain(update_all_distributions.si(), send_update_notifications.si()).delay()
    else:
        update_all_distributions.delay()


@shared_task
def update_all_distributions():
    Distribution.objects.update_all()


@shared_task
def send_update_notifications(should_repeat: bool = False):
    Distribution.objects.send_update_notifications(
        show_editable=PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
        should_repeat=should_repeat or PACKAGE_MONITOR_REPEAT_NOTIFICATIONS,
    )
