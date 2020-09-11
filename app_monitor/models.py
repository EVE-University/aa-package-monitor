from django.db import models

from .managers import DistributionManager


class AppMonitor(models.Model):
    # Meta model for app permissions

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("basic_access", "Can access this app"),)


class Distribution(models.Model):
    """A Python distribution"""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(default="")
    apps = models.TextField(default="")
    installed_version = models.CharField(max_length=64, default="")
    latest_version = models.CharField(max_length=64, default="")
    is_outdated = models.BooleanField(default=None, null=True, db_index=True)
    website_url = models.TextField(default="")
    updated_at = models.DateTimeField(auto_now=True)

    objects = DistributionManager()

    def __str__(self) -> str:
        return self.name
