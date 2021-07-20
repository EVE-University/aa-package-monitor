from celery import shared_task

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .models import Distribution

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@shared_task(time_limit=3600)
def update_distributions():
    Distribution.objects.update_all()
