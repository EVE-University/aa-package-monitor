import logging

from celery import shared_task

from .models import Distribution


logger = logging.getLogger(__name__)


@shared_task
def update_distributions():
    Distribution.objects.update_all()
