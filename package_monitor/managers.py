from typing import Dict, Set

import importlib_metadata
from packaging.utils import canonicalize_name
from packaging.version import parse as version_parse

from django.db import models, transaction

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_EXCLUDE_PACKAGES,
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
    PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES,
)
from .core import (
    DistributionPackage,
    compile_package_requirements,
    fetch_relevant_packages,
    update_packages_from_pypi,
)

TERMINAL_MAX_LINE_LENGTH = 4095

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def _none_2_empty(text) -> str:
    """Translate None to empty string."""
    if text is None:
        return ""
    return text


class DistributionQuerySet(models.QuerySet):
    def outdated_count(self) -> int:
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
    def update_all(self, use_threads=False) -> int:
        """Update the list of relevant distribution packages in the database."""
        logger.info(
            f"Started refreshing approx. {self.count()} distribution packages..."
        )
        packages = fetch_relevant_packages(importlib_metadata.distributions())
        requirements = compile_package_requirements(
            packages, importlib_metadata.distributions()
        )
        update_packages_from_pypi(packages, requirements, use_threads)
        self._save_packages(packages, requirements)
        packages_count = len(packages)
        logger.info(f"Completed refreshing {packages_count} distribution packages")
        return packages_count

    def _save_packages(
        self, packages: Dict[str, DistributionPackage], requirements: dict
    ) -> None:
        """Save the given package information into the model."""

        def metadata_value(dist, prop: str) -> str:
            return (
                dist.metadata[prop]
                if dist and dist.metadata.get(prop) != "UNKNOWN"
                else ""
            )

        def packages_lookup(packages: dict, name: str, attr: str, default=None):
            package = packages.get(canonicalize_name(name))
            return getattr(package, attr) if package else default

        with transaction.atomic():
            self.all().delete()
            objs = list()
            for package_name, package in packages.items():
                is_outdated = (
                    version_parse(package.current) < version_parse(package.latest)
                    if package.current
                    and package.latest
                    and str(package.current) == str(package.distribution.version)
                    else None
                )
                if package_name in requirements:
                    used_by = [
                        {
                            "name": package_name,
                            "homepage_url": metadata_value(
                                packages_lookup(packages, package_name, "distribution"),
                                "Home-page",
                            ),
                            "requirements": [str(obj) for obj in package_requirements],
                        }
                        for package_name, package_requirements in requirements[
                            package_name
                        ].items()
                    ]
                else:
                    used_by = []

                name = _none_2_empty(package.distribution.metadata["Name"])
                apps = sorted(package.apps, key=str.casefold)
                installed_version = _none_2_empty(package.distribution.version)
                latest_version = str(package.latest) if package.latest else ""
                description = _none_2_empty(
                    metadata_value(package.distribution, "Summary")
                )
                website_url = _none_2_empty(
                    metadata_value(package.distribution, "Home-page")
                )
                obj = self.model(
                    name=name,
                    apps=apps,
                    used_by=used_by,
                    installed_version=installed_version,
                    latest_version=latest_version,
                    is_outdated=is_outdated,
                    is_editable=package.is_editable(),
                    description=description,
                    website_url=website_url,
                )
                obj.calc_has_installed_apps()
                objs.append(obj)
            self.bulk_create(objs)


DistributionManager = DistributionManagerBase.from_queryset(DistributionQuerySet)
