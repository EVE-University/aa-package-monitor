import concurrent.futures
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import importlib_metadata
import requests
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import parse as version_parse

from django.apps import apps as django_apps

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

# max workers used when fetching info from PyPI for packages
MAX_THREAD_WORKERS = 30


@dataclass
class DistributionPackage:
    """A parsed distribution package."""

    name: str
    current: str
    requirements: List[Requirement] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    latest: str = ""
    homepage_url: str = ""
    summary: str = ""

    @property
    def name_normalized(self) -> str:
        return canonicalize_name(self.name)

    def is_outdated(self) -> Optional[bool]:
        """Is this package outdated?"""
        if self.current and self.latest:
            return version_parse(self.current) < version_parse(self.latest)
        return None

    def is_editable(self):
        """Is distribution an editable install?"""
        for path_item in sys.path:
            egg_link = os.path.join(path_item, self.name + ".egg-link")
            if os.path.isfile(egg_link):
                return True
        return False

    @classmethod
    def create_from_distribution(
        cls, dist: importlib_metadata.Distribution, disable_app_check=False
    ):
        """Create new object from an importlib distribution."""
        obj = cls(
            name=dist.name,
            current=dist.version,
            requirements=_parse_requirements(dist.requires),
            homepage_url=dist_metadata_value(dist, "Home-page"),
            summary=dist_metadata_value(dist, "Summary"),
        )
        dist_files = [
            "/" + str(f) for f in dist.files if str(f).endswith("__init__.py")
        ]
        if not disable_app_check:
            for dist_file in dist_files:
                for app in django_apps.get_app_configs():
                    my_file = app.module.__file__
                    if my_file.endswith(dist_file):
                        obj.apps.append(app.name)
                        break
        return obj


def gather_distribution_packages() -> Dict[str, DistributionPackage]:
    """Gather distribution packages and detect Django apps."""
    packages = [
        DistributionPackage.create_from_distribution(dist)
        for dist in importlib_metadata.distributions()
        if dist.metadata["Name"]
    ]
    return {obj.name_normalized: obj for obj in packages}


def _parse_requirements(requires: list) -> List[Requirement]:
    """Parse requirements from a distribution and return them.

    Invalid requirements will be ignored.
    """
    requirements = list()
    if requires:
        for r in requires:
            try:
                requirements.append(Requirement(r))
            except InvalidRequirement:
                pass
    return requirements


def compile_package_requirements(packages: Dict[str, DistributionPackage]) -> dict:
    """Consolidate requirements from all known distributions and known packages"""
    requirements = dict()
    for dist in importlib_metadata.distributions():
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

        current_python_version = version_parse(
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )
        consolidated_requirements = SpecifierSet()
        if package_name in requirements:
            for _, specifier in requirements[package_name].items():
                consolidated_requirements &= specifier

        package = packages[package_name]
        current_version = version_parse(package.current)
        current_is_prerelease = (
            str(current_version) == str(package.current)
            and current_version.is_prerelease
        )
        logger.info(
            f"Fetching info for distribution package '{package.name}' " "from PyPI"
        )
        r = requests.get(f"https://pypi.org/pypi/{package.name}/json", timeout=(5, 30))
        if r.status_code == requests.codes.ok:
            pypi_info = r.json()
            latest = ""
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
                    f"Could not find a release of '{package.name}' "
                    f"that matches all requirements: '{consolidated_requirements}''"
                )
        else:
            if r.status_code == 404:
                logger.info(f"Package '{package.name}' is not registered in PyPI")
            else:
                logger.warning(
                    "Failed to retrieve infos from PyPI for "
                    f"package '{package.name}'. "
                    f"Status code: {r.status_code}, "
                    f"response: {r.content}"
                )
            latest = ""

        packages[package_name].latest = latest

    if use_threads:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        ) as executor:
            executor.map(thread_update_latest_from_pypi, packages.keys())
    else:
        for package_name in packages.keys():
            thread_update_latest_from_pypi(package_name)


def dist_metadata_value(dist: importlib_metadata.Distribution, prop: str) -> str:
    """Metadata value from distribution or empty string."""
    if dist and dist.metadata[prop] and dist.metadata[prop] != "UNKNOWN":
        return dist.metadata[prop]
    return ""
