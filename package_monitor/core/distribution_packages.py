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
from packaging.version import InvalidVersion
from packaging.version import parse as version_parse

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__

from . import metadata_helpers

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

# max workers used when fetching info from PyPI for packages
MAX_THREAD_WORKERS = 30


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
    """Fetch the latest versions for given packages from PyPI in accordance
    with the given requirements and updates the packages.
    """

    def thread_update_latest_from_pypi(package_name: str) -> None:
        """Retrieves latest valid version from PyPI and updates packages

        Note: This inner function can run as thread
        """
        nonlocal packages

        current_package = packages[package_name]
        pypi_data = _fetch_data_from_pypi(current_package)
        if pypi_data:
            consolidated_requirements = _calc_consolidated_requirements(
                package_name, requirements
            )
            latest, pypi_url = _determine_versions(
                current_package, consolidated_requirements, pypi_data
            )
        else:
            latest, pypi_url = "", ""
        packages[package_name].latest = latest
        packages[package_name].homepage_url = pypi_url

    def _fetch_data_from_pypi(package) -> Optional[dict]:
        """Fetch data for a package from PyPI."""

        logger.info(
            f"Fetching info for distribution package '{package.name}' from PyPI"
        )

        r = requests.get(f"https://pypi.org/pypi/{package.name}/json", timeout=(5, 30))
        if r.status_code != requests.codes.ok:
            if r.status_code == 404:
                logger.info(f"Package '{package.name}' is not registered in PyPI")
            else:
                logger.warning(
                    "Failed to retrieve infos from PyPI for "
                    f"package '{package.name}'. "
                    f"Status code: {r.status_code}, "
                    f"response: {r.content}"
                )
            return None

        pypi_data = r.json()
        return pypi_data

    def _determine_versions(package, consolidated_requirements, pypi_data):
        current_is_prerelease = _is_current_pre_release(package)
        current_python_version = version_parse(
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )
        latest = ""
        pypi_info = pypi_data.get("info")
        pypi_url = pypi_info.get("project_url", "") if pypi_info else ""
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
                    current_is_prerelease or not my_release.is_prerelease
                ):
                    if len(consolidated_requirements) > 0:
                        is_valid = my_release in consolidated_requirements
                    else:
                        is_valid = True

                    if is_valid and (not latest or my_release > version_parse(latest)):
                        latest = release
            except InvalidVersion:
                logger.warning(
                    "%s: Ignoring release with invalid version: %s",
                    package.name,
                    release,
                )
            except InvalidSpecifier:
                logger.warning(
                    "%s: Ignoring release with invalid requires_python: %s",
                    package.name,
                    requires_python,
                )
        if not latest:
            logger.warning(
                f"Could not find a release of '{package.name}' "
                f"that matches all requirements: '{consolidated_requirements}''"
            )
        return latest, pypi_url

    def _is_current_pre_release(package):
        current_version = version_parse(package.current)
        current_is_prerelease = (
            str(current_version) == str(package.current)
            and current_version.is_prerelease
        )
        return current_is_prerelease

    def _calc_consolidated_requirements(package_name, requirements):
        consolidated_requirements = SpecifierSet()
        if package_name in requirements:
            for _, specifier in requirements[package_name].items():
                consolidated_requirements &= specifier
        return consolidated_requirements

    if use_threads:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        ) as executor:
            executor.map(thread_update_latest_from_pypi, packages.keys())
    else:
        for package_name in packages.keys():
            thread_update_latest_from_pypi(package_name)
