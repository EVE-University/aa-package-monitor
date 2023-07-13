"""Handle parsed distribution packages."""

import concurrent.futures
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import importlib_metadata
import requests
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from packaging.version import parse as version_parse

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__

from . import metadata_helpers

MAX_THREAD_WORKERS = 30

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@dataclass
class DistributionPackage:
    """A parsed distribution package."""

    name: str
    current: str
    is_editable: bool
    requirements: List[Requirement] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    latest: str = ""
    homepage_url: str = ""
    summary: str = ""

    def __str__(self) -> str:
        return f"{self.name} {self.current}"

    @property
    def name_normalized(self) -> str:
        return canonicalize_name(self.name)

    def is_outdated(self) -> Optional[bool]:
        """Is this package outdated?"""
        if self.current and self.latest:
            return version_parse(self.current) < version_parse(self.latest)
        return None

    def is_prerelease(self) -> bool:
        """Determine if this package is a prerelease."""
        current_version = version_parse(self.current)
        current_is_prerelease = (
            str(current_version) == str(self.current) and current_version.is_prerelease
        )
        return current_is_prerelease

    def calc_consolidated_requirements(self, requirements: dict) -> SpecifierSet:
        """Determine consolidated requirements for this package."""
        consolidated_requirements = SpecifierSet()
        if self.name_normalized in requirements:
            for _, specifier in requirements[self.name_normalized].items():
                consolidated_requirements &= specifier
        return consolidated_requirements

    def update_from_pypi(self, requirements: dict) -> bool:
        """Update from PyPI.

        Return True if update successful, else False.
        """

        pypi_data = self._fetch_data_from_pypi()
        if not pypi_data:
            return False

        consolidated_requirements = self.calc_consolidated_requirements(requirements)
        current_python_version = self._current_python_version()
        latest = ""
        for release, release_details in pypi_data["releases"].items():
            requires_python = ""
            try:
                release_detail = (
                    release_details[-1] if len(release_details) > 0 else None
                )
                if release_detail:
                    if release_detail["yanked"]:
                        continue
                    if (
                        requires_python := release_detail.get("requires_python")
                    ) and current_python_version not in SpecifierSet(requires_python):
                        continue

                my_release = version_parse(release)
                if str(my_release) == str(release) and (
                    self.is_prerelease() or not my_release.is_prerelease
                ):
                    if len(consolidated_requirements) > 0:
                        is_valid = my_release in consolidated_requirements
                    else:
                        is_valid = True

                    if is_valid and (not latest or my_release > version_parse(latest)):
                        latest = release

            except InvalidVersion:
                logger.info(
                    "%s: Ignoring release with invalid version: %s",
                    self.name,
                    release,
                )
            except InvalidSpecifier:
                logger.info(
                    "%s: Ignoring release with invalid requires_python: %s",
                    self.name,
                    requires_python,
                )

        if not latest:
            logger.warning(
                f"Could not find a release of '{self.name}' "
                f"that matches all requirements: '{consolidated_requirements}''"
            )

        self.latest = latest

        pypi_info = pypi_data.get("info")
        pypi_url = pypi_info.get("project_url", "") if pypi_info else ""
        self.homepage_url = pypi_url
        return True

    def _fetch_data_from_pypi(self) -> Optional[dict]:
        """Fetch data for a package from PyPI."""

        logger.info(f"Fetching info for distribution package '{self.name}' from PyPI")

        url = f"https://pypi.org/pypi/{self.name}/json"
        r = requests.get(url, timeout=(5, 30))
        if r.status_code != requests.codes.ok:
            if r.status_code == 404:
                logger.info(f"Package '{self.name}' is not registered in PyPI")
            else:
                logger.warning(
                    "Failed to retrieve infos from PyPI for "
                    f"package '{self.name}'. "
                    f"Status code: {r.status_code}, "
                    f"response: {r.content}"
                )
            return None

        pypi_data = r.json()
        return pypi_data

    @staticmethod
    def _current_python_version() -> Version:
        current_python_version = version_parse(
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )
        return current_python_version

    @classmethod
    def create_from_metadata_distribution(
        cls, dist: importlib_metadata.Distribution, disable_app_check=False
    ):
        """Create new object from a metadata distribution.

        This is the only place where we are accessing the importlib metadata API
        for a specific distribution package and are thus storing
        all needed information about that package in our new object.
        Should additional information be needed sometimes it should be fetched here too.
        """
        obj = cls(
            name=dist.name,
            current=dist.version,
            is_editable=metadata_helpers.is_distribution_editable(dist),
            requirements=metadata_helpers.parse_requirements(dist),
            summary=metadata_helpers.metadata_value(dist, "Summary"),
        )
        if not disable_app_check:
            obj.apps = metadata_helpers.identify_installed_django_apps(dist)
        return obj


def gather_distribution_packages() -> Dict[str, DistributionPackage]:
    """Gather distribution packages and detect Django apps."""
    packages = [
        DistributionPackage.create_from_metadata_distribution(dist)
        for dist in importlib_metadata.distributions()
        if dist.metadata["Name"]
    ]
    return {obj.name_normalized: obj for obj in packages}


def compile_package_requirements(packages: Dict[str, DistributionPackage]) -> dict:
    """Consolidate requirements from all known distributions and known packages"""
    requirements = dict()
    for package in packages.values():
        for requirement in package.requirements:
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
                    requirements[requirement_name][package.name] = requirement.specifier

    return requirements


def update_packages_from_pypi(
    packages: Dict[str, DistributionPackage], requirements: dict, use_threads=False
) -> None:
    """Update packages with latest versions and URL from PyPI in accordance
    with the given requirements and updates the packages.
    """

    def thread_update_latest_from_pypi(current_package: DistributionPackage) -> None:
        """Retrieves latest valid version from PyPI and updates packages
        Note: This inner function can run as thread
        """
        nonlocal packages

        current_package.update_from_pypi(requirements)

    if use_threads:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        ) as executor:
            executor.map(thread_update_latest_from_pypi, packages.values())
    else:
        for package in packages.values():
            thread_update_latest_from_pypi(package)
