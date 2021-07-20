import json

from django.db import models

from .managers import DistributionManager


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("basic_access", "Can access this app"),)


class Distribution(models.Model):
    """A Python distribution package"""

    name = models.CharField(
        max_length=255, unique=True, help_text="Name of this package"
    )
    description = models.TextField(default="", help_text="Description of this package")
    apps = models.TextField(
        default="",
        help_text="List of installed Django apps included in this package (JSON)",
    )
    has_installed_apps = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this package has installed Django apps",
    )
    used_by = models.TextField(
        default="",
        help_text="List of other distribution packages using this package (JSON)",
    )
    installed_version = models.CharField(
        max_length=64,
        default="",
        help_text="Currently installed version of this package",
    )
    latest_version = models.CharField(
        max_length=64,
        default="",
        help_text="Latest stable version available for this package",
    )
    is_outdated = models.BooleanField(
        default=None,
        null=True,
        db_index=True,
        help_text="A package is outdated when there is a newer stable version available",
    )
    website_url = models.TextField(
        default="", help_text="URL to the home page of this package"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date & time this data was last updated"
    )

    objects = DistributionManager()

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.calc_has_installed_apps()
        super().save(*args, **kwargs)

    def calc_has_installed_apps(self) -> None:
        self.has_installed_apps = bool(json.loads(self.apps))

    @property
    def pip_install_version(self) -> str:
        return (
            f"{self.name}=={self.latest_version}" if self.latest_version else self.name
        )
