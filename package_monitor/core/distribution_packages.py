"""Core logic for parsed distribution packages."""

import asyncio
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import aiohttp
import importlib_metadata
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from packaging.version import parse as version_parse

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__
from package_monitor.app_settings import PACKAGE_MONITOR_CUSTOM_REQUIREMENTS

from . import metadata_helpers

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
        """Return normalized name."""
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

    async def update_from_pypi_async(
        self, requirements: dict, session: aiohttp.ClientSession
    ) -> bool:
        """Update latest version and URL from PyPI.

        Return True if update was successful, else False.
        """

        pypi_data = await self._fetch_data_from_pypi_async(session)
        if not pypi_data:
            return False

        system_python_version = determine_system_python_version()
        latest = self._determine_latest_version(
            pypi_data["releases"], requirements, system_python_version
        )

        if not latest:
            logger.warning(
                "%s: Could not find any release that matches all requirements", self
            )

        self.latest = latest

        pypi_info = pypi_data.get("info")
        pypi_url = pypi_info.get("project_url", "") if pypi_info else ""
        self.homepage_url = pypi_url
        return True

    async def _fetch_data_from_pypi_async(
        self, session: aiohttp.ClientSession
    ) -> Optional[dict]:
        """Fetch data for a package from PyPI and return it
        or return None if there was an API error.
        """

        logger.info(f"Fetching info for distribution package '{self.name}' from PyPI")

        url = f"https://pypi.org/pypi/{self.name}/json"
        async with session.get(url) as resp:
            if not resp.ok:
                if resp.status == 404:
                    logger.info("Package '%s' is not registered in PyPI", self.name)
                else:
                    logger.warning(
                        "Failed to retrieve infos from PyPI for "
                        "package '%s'. "
                        "Status code: %d, "
                        "response: %s",
                        self.name,
                        resp.status,
                        await resp.text(),
                    )
                return None

            pypi_data = await resp.json()
            return pypi_data

    def _determine_latest_version(
        self, pypi_data_releases, requirements, system_python_version
    ):
        """Determine latest valid version available on PyPI."""
        consolidated_requirements = self.calc_consolidated_requirements(requirements)
        latest = ""
        for release, release_details in pypi_data_releases.items():
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
                    ) and system_python_version not in SpecifierSet(requires_python):
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

        return latest

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
    requirements = defaultdict(dict)

    # add requirements from all packages
    for package in packages.values():
        for requirement in package.requirements:
            _add_valid_requirement(requirements, requirement, package.name, packages)

    # add requirements from settings (if any)
    for requirement_string in PACKAGE_MONITOR_CUSTOM_REQUIREMENTS:
        try:
            requirement = Requirement(requirement_string)
        except InvalidRequirement:
            continue
        _add_valid_requirement(requirements, requirement, "CUSTOM", packages)

    return dict(requirements)


def _add_valid_requirement(
    requirements: dict, requirement: Requirement, package_name: str, packages: dict
):
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
            requirements[requirement_name][package_name] = requirement.specifier


def update_packages_from_pypi(
    packages: Dict[str, DistributionPackage], requirements: dict
) -> None:
    """Update packages with latest versions and URL from PyPI in accordance
    with the given requirements and updates the packages.
    """

    async def update_packages_from_pypi_async() -> None:
        """Update packages from PyPI concurrently."""
        async with aiohttp.ClientSession() as session:
            tasks = [
                asyncio.create_task(
                    package.update_from_pypi_async(requirements, session)
                )
                for package in packages.values()
            ]
            await asyncio.gather(*tasks)

    asyncio.run(update_packages_from_pypi_async())


def determine_system_python_version() -> Version:
    """Return current Python version of this system."""
    result = version_parse(
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}"
    )
    return result
