import concurrent.futures
import json
import sys
from collections import namedtuple
from typing import List

import requests
from importlib_metadata import distributions
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import parse as version_parse

from django.apps import apps as django_apps
from django.db import models, transaction

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)
_DistributionInfo = namedtuple("_DistributionInfo", ["name", "files", "distribution"])


def _none_2_empty(text) -> str:
    """Translate None to empty string."""
    if text is None:
        return ""
    return text


def _parse_requirements(requires: list) -> List[Requirement]:
    """Parses requirements from a distribution and returns it.
    Invalid requirements will be ignored
    """
    requirements = list()
    if requires:
        for r in requires:
            try:
                requirements.append(Requirement(r))
            except InvalidRequirement:
                pass

    return requirements


class DistributionQuerySet(models.QuerySet):
    def outdated_count(self) -> int:
        return self.filter(is_outdated=True).count()


class DistributionManager(models.Manager):

    # max workers used when fetching info from PyPI for packages
    MAX_THREAD_WORKERS = 10

    def get_queryset(self) -> models.QuerySet:
        return DistributionQuerySet(self.model, using=self._db)

    def currently_selected(self) -> models.QuerySet:
        """Currently selected packages based on global settings,
        e.g. related to installed apps vs. all packages
        """
        if PACKAGE_MONITOR_SHOW_ALL_PACKAGES:
            return self.all()
        else:
            qs = self.filter(has_installed_apps=True)
            if PACKAGE_MONITOR_INCLUDE_PACKAGES:
                qs |= self.filter(name__in=PACKAGE_MONITOR_INCLUDE_PACKAGES)
            return qs

    def update_all(self, use_threads=False) -> int:
        """Updates the list of relevant distribution packages in the database"""
        logger.info(
            f"Started refreshing approx. {self.count()} distribution packages..."
        )
        packages = self._select_relevant_packages()
        requirements = self._compile_package_requirements(packages)
        self._fetch_versions_from_pypi(packages, requirements, use_threads)
        self._save_packages(packages, requirements)
        packages_count = len(packages)
        logger.info(f"Completed refreshing {packages_count} distribution packages")
        return packages_count

    @classmethod
    def _select_relevant_packages(cls) -> dict:
        """returns subset of distribution packages with packages of interest

        Interesting packages are related to installed apps or explicitely defined
        """

        def create_or_update_package(dist, packages: dict) -> None:
            if dist.name not in packages:
                packages[dist.name] = {
                    "name": dist.name,
                    "apps": list(),
                    "current": dist.distribution.version,
                    "requirements": _parse_requirements(dist.distribution.requires),
                    "distribution": dist.distribution,
                }

        packages = dict()
        for dist in cls._distribution_packages_amended():
            create_or_update_package(dist, packages)
            for app in django_apps.get_app_configs():
                my_file = app.module.__file__
                for dist_file in dist.files:
                    if my_file.endswith(dist_file):
                        packages[dist.name]["apps"].append(app.name)
                        break

        return packages

    @staticmethod
    def _distribution_packages_amended() -> list:
        """returns the list of all known distribution packages with amended infos"""
        return [
            _DistributionInfo(
                name=canonicalize_name(dist.metadata["Name"]),
                distribution=dist,
                files=[
                    "/" + str(f) for f in dist.files if str(f).endswith("__init__.py")
                ],
            )
            for dist in distributions()
            if dist.metadata["Name"]
        ]

    @staticmethod
    def _compile_package_requirements(packages: dict) -> dict:
        """returns all requirements in consolidated from all known distributions
        for given packages
        """
        requirements = dict()
        for dist in distributions():
            if dist.requires:
                for requirement in _parse_requirements(dist.requires):
                    requirement_name = canonicalize_name(requirement.name)
                    if requirement_name in packages:
                        if requirement.marker:
                            try:
                                is_valid = requirement.marker.evaluate()
                            except (UndefinedEnvironmentName, UndefinedComparison):
                                is_valid = False
                        else:
                            is_valid = True

                        if is_valid:
                            if requirement_name not in requirements:
                                requirements[requirement_name] = dict()

                            requirements[requirement_name][
                                dist.metadata["Name"]
                            ] = requirement.specifier

        return requirements

    @classmethod
    def _fetch_versions_from_pypi(
        cls, packages: dict, requirements: dict, use_threads=False
    ) -> None:
        """fetches the latest versions for given packages from PyPI in accordance
        with the given requirements and updates the packages
        """

        def thread_update_latest_from_pypi(package_name: str) -> None:
            """Retrieves latest valid version from PyPI and updates packages

            Note: This inner function runs as thread
            """
            nonlocal packages

            current_python_version = version_parse(
                f"{sys.version_info.major}.{sys.version_info.minor}"
                f".{sys.version_info.micro}"
            )
            consolidated_requirements = SpecifierSet()
            if package_name in requirements:
                for _, specifier in requirements[package_name].items():
                    consolidated_requirements &= specifier

            package = packages[package_name]
            current_version = version_parse(package["current"])
            current_is_prerelease = (
                str(current_version) == str(package["current"])
                and current_version.is_prerelease
            )
            package_name_with_case = package["distribution"].metadata["Name"]
            logger.info(
                f"Fetching info for distribution package '{package_name_with_case}' "
                "from PyPI"
            )
            r = requests.get(
                f"https://pypi.org/pypi/{package_name_with_case}/json", timeout=(5, 30)
            )
            if r.status_code == requests.codes.ok:
                pypi_info = r.json()
                latest = None
                for release, release_details in pypi_info["releases"].items():
                    release_detail = (
                        release_details[-1] if len(release_details) > 0 else None
                    )
                    if not release_detail or (
                        not release_detail["yanked"]
                        and (
                            "requires_python" not in release_detail
                            or not release_detail["requires_python"]
                            or current_python_version
                            in SpecifierSet(release_detail["requires_python"])
                        )
                    ):
                        my_release = version_parse(release)
                        if str(my_release) == str(release) and (
                            current_is_prerelease or not my_release.is_prerelease
                        ):
                            if len(consolidated_requirements) > 0:
                                is_valid = my_release in consolidated_requirements
                            else:
                                is_valid = True

                            if is_valid and (
                                not latest or my_release > version_parse(latest)
                            ):
                                latest = release

                if not latest:
                    logger.warning(
                        f"Could not find a release of '{package_name_with_case}' "
                        f"that matches all requirements: '{consolidated_requirements}''"
                    )
            else:
                if r.status_code == 404:
                    logger.info(
                        f"Package '{package_name_with_case}' is not registered in PyPI"
                    )
                else:
                    logger.warning(
                        "Failed to retrive infos from PyPI for "
                        f"package '{package_name_with_case}'. "
                        f"Status code: {r.status_code}, "
                        f"response: {r.content}"
                    )
                latest = None

            packages[package_name]["latest"] = latest

        if use_threads:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=cls.MAX_THREAD_WORKERS
            ) as executor:
                executor.map(thread_update_latest_from_pypi, packages.keys())
        else:
            for package_name in packages.keys():
                thread_update_latest_from_pypi(package_name)

    def _save_packages(self, packages: dict, requirements: dict) -> None:
        """Saves the given package information into the model"""

        def metadata_value(dist, prop: str) -> str:
            return (
                dist.metadata[prop]
                if dist and dist.metadata.get(prop) != "UNKNOWN"
                else ""
            )

        def packages_lookup(packages: dict, name: str, attr: str, default=None):
            package = packages.get(canonicalize_name(name))
            return package.get(attr) if package else default

        with transaction.atomic():
            self.all().delete()
            distributions = list()
            for package_name, package in packages.items():
                current = package.get("current")
                latest = package.get("latest")
                is_outdated = (
                    version_parse(current) < version_parse(latest)
                    if current
                    and latest
                    and str(current) == str(package["distribution"].version)
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

                name = _none_2_empty(package["distribution"].metadata["Name"])
                apps = _none_2_empty(
                    json.dumps(sorted(package["apps"], key=str.casefold))
                )
                used_by = _none_2_empty(json.dumps(used_by))
                installed_version = _none_2_empty(package["distribution"].version)
                latest_version = str(package["latest"]) if package["latest"] else ""
                description = _none_2_empty(
                    metadata_value(package["distribution"], "Summary")
                )
                website_url = _none_2_empty(
                    metadata_value(package["distribution"], "Home-page")
                )
                obj = self.model(
                    name=name,
                    apps=apps,
                    used_by=used_by,
                    installed_version=installed_version,
                    latest_version=latest_version,
                    is_outdated=is_outdated,
                    description=description,
                    website_url=website_url,
                )
                obj.calc_has_installed_apps()
                distributions.append(obj)

            self.bulk_create(distributions)
