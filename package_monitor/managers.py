"""Managers for Package Monitor."""

from typing import Dict, Set

from django.db import models

from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_admins
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_EXCLUDE_PACKAGES,
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_NOTIFICATIONS_ENABLED,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
    PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
)
from .core.distribution_packages import (
    DistributionPackage,
    compile_package_requirements,
    gather_distribution_packages,
    update_packages_from_pypi,
)

TERMINAL_MAX_LINE_LENGTH = 4095

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class DistributionQuerySet(models.QuerySet):
    """QuerySets for Distribution."""

    def outdated_count(self) -> int:
        """Return count of outdated packages."""
        return self.filter(is_outdated=True).count()

    def build_install_command(self) -> str:
        """Build install command from all distribution packages in this query."""
        result = "pip install"
        for dist in self.exclude(latest_version=""):
            version_string = dist.pip_install_version
            if len(result) + len(version_string) + 1 > TERMINAL_MAX_LINE_LENGTH:
                break
            result = f"{result} {version_string}"
        return result

    def filter_visible(self) -> models.QuerySet:
        """Filter to include visible packages only based on current settings."""
        if PACKAGE_MONITOR_SHOW_ALL_PACKAGES:
            qs = self.all()
        else:
            qs = self.filter(has_installed_apps=True)
        if PACKAGE_MONITOR_INCLUDE_PACKAGES:
            qs |= self.filter(name__in=PACKAGE_MONITOR_INCLUDE_PACKAGES)
        if PACKAGE_MONITOR_EXCLUDE_PACKAGES:
            qs = qs.exclude(name__in=PACKAGE_MONITOR_EXCLUDE_PACKAGES)
        if not PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES:
            qs = qs.exclude(is_editable=True)
        return qs

    def names(self) -> Set[str]:
        """Return QS as set of names."""
        return set(self.values_list("name", flat=True))


class DistributionManagerBase(models.Manager):
    """Manager for Distribution."""

    def update_all(self, notifications_disabled: bool = False) -> int:
        """Update the list of relevant distribution packages in the database."""
        logger.info(
            f"Started refreshing approx. {self.count()} distribution packages..."
        )
        packages = gather_distribution_packages()
        requirements = compile_package_requirements(packages)
        update_packages_from_pypi(packages, requirements)
        self._save_packages(
            packages=packages,
            requirements=requirements,
            notifications_disabled=notifications_disabled,
        )
        packages_count = len(packages)
        logger.info(f"Completed refreshing {packages_count} distribution packages")
        return packages_count

    def _save_packages(
        self,
        packages: Dict[str, DistributionPackage],
        requirements: dict,
        notifications_disabled: bool,
    ) -> None:
        """Save the given package information into the model."""

        for package_name, package in packages.items():
            logger.debug("Updating package: %s", package)
            if package_name in requirements:
                used_by = [
                    {
                        "name": package_name,
                        "homepage_url": (
                            packages[package_name].homepage_url
                            if packages.get(package_name)
                            else ""
                        ),
                        "requirements": [str(obj) for obj in package_requirements],
                    }
                    for package_name, package_requirements in requirements[
                        package_name
                    ].items()
                ]
            else:
                used_by = []

            latest_notified_version = self._notify_about_update(
                package=package, notifications_disabled=notifications_disabled
            )

            defaults = {
                "apps": sorted(package.apps, key=str.casefold),
                "used_by": used_by,
                "installed_version": package.current,
                "latest_version": package.latest,
                "is_outdated": package.is_outdated(),
                "is_editable": package.is_editable,
                "description": package.summary,
                "website_url": package.homepage_url,
            }
            if latest_notified_version:
                defaults["latest_notified_version"] = latest_notified_version
            self.update_or_create(name=package.name, defaults=defaults)
        package_names = {obj.name for obj in packages.values()}
        self.exclude(name__in=package_names).delete()

    def _notify_about_update(self, package, notifications_disabled: bool) -> str:
        """Notify admins when a new update is available for this package."""
        if (
            notifications_disabled
            or not PACKAGE_MONITOR_NOTIFICATIONS_ENABLED
            or package.is_editable
            and not PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES
        ):
            return ""
        try:
            obj = self.get(name=package.name)
        except self.model.DoesNotExist:
            latest_notified_version = ""
        else:
            latest_notified_version = obj.latest_notified_version
        if package.is_outdated() and latest_notified_version != package.latest:
            latest_notified_version = package.latest
            title = f"Update available: {package.name} {package.latest}"
            message = (
                f"There is an update available: {package.name} {package.current} "
                f"=> {package.latest}\n"
                "This message was automatically generated by Package Monitor."
            )
            notify_admins(message=message, title=title)
        return latest_notified_version


DistributionManager = DistributionManagerBase.from_queryset(DistributionQuerySet)
