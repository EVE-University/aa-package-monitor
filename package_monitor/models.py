from typing import Optional

from packaging.version import parse as version_parse

from django.db import models

from .managers import DistributionManager

MAX_LENGTH_VERSION_STRING = 64


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
    apps = models.JSONField(
        default=list,
        help_text="List of installed Django apps included in this package",
    )
    has_installed_apps = models.BooleanField(
        default=False,
        help_text="Whether this package has installed Django apps",
    )
    used_by = models.JSONField(
        default=list,
        help_text="List of other distribution packages using this package",
    )
    installed_version = models.CharField(
        max_length=MAX_LENGTH_VERSION_STRING,
        default="",
        help_text="Currently installed version of this package",
    )
    latest_version = models.CharField(
        max_length=MAX_LENGTH_VERSION_STRING,
        default="",
        help_text="Latest stable version available for this package",
    )
    is_outdated = models.BooleanField(
        default=None,
        null=True,
        help_text="A package is outdated when there is a newer stable version available",
    )
    is_editable = models.BooleanField(
        default=None,
        null=True,
        help_text="Package has been installed in editable mode, i.e. pip install -e",
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
        self.has_installed_apps = bool(self.apps)
        self.is_outdated = self.calc_is_outdated()
        super().save(*args, **kwargs)

    def calc_is_outdated(self) -> Optional[bool]:
        if self.installed_version and self.latest_version:
            return version_parse(self.installed_version) < version_parse(
                self.latest_version
            )
        return None

    @property
    def pip_install_version(self) -> str:
        return (
            f"{self.name}=={self.latest_version}" if self.latest_version else self.name
        )
