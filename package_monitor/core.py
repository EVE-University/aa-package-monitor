import concurrent.futures
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List

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
class DistributionWrapped:
    """Distribution with some additional information."""

    name: str
    distribution: importlib_metadata.Distribution
    files: List[str] = field(default_factory=list)

    @classmethod
    def from_distribution(
        cls, dist: importlib_metadata.Distribution
    ) -> "DistributionWrapped":
        return cls(
            name=canonicalize_name(dist.metadata["Name"]),
            distribution=dist,
            files=["/" + str(f) for f in dist.files if str(f).endswith("__init__.py")],
        )

    @classmethod
    def from_distributions(
        cls, distributions: Iterable[importlib_metadata.Distribution]
    ) -> "DistributionWrapped":
        return [
            DistributionWrapped.from_distribution(dist)
            for dist in distributions
            if dist.metadata["Name"]
        ]


@dataclass
class DistributionPackage:
    """A distribution package."""

    name: str
    current: str
    distribution: importlib_metadata.Distribution
    requirements: List[Requirement] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    latest: str = ""


def fetch_relevant_packages(
    distributions: Iterable[importlib_metadata.Distribution],
) -> Dict[str, DistributionPackage]:
    """Fetch distribution packages with packages relevant for this Django installation"""
    packages = dict()
    for dist in DistributionWrapped.from_distributions(distributions):
        if dist.name not in packages:
            packages[dist.name] = DistributionPackage(
                **{
                    "name": dist.name,
                    "current": dist.distribution.version,
                    "requirements": _parse_requirements(dist.distribution.requires),
                    "distribution": dist.distribution,
                }
            )
        for dist_file in dist.files:
            for app in django_apps.get_app_configs():
                my_file = app.module.__file__
                if my_file.endswith(dist_file):
                    packages[dist.name].apps.append(app.name)
                    break
    return packages


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


def compile_package_requirements(
    packages: Dict[str, DistributionPackage],
    distributions: Iterable[importlib_metadata.Distribution],
) -> dict:
    """Consolidate requirements from all known distributions and known packages"""
    requirements = dict()
    for dist in distributions:
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
        current_version = version_parse(package.current)
        current_is_prerelease = (
            str(current_version) == str(package.current)
            and current_version.is_prerelease
        )
        package_name_with_case = package.distribution.metadata["Name"]
        logger.info(
            f"Fetching info for distribution package '{package_name_with_case}' "
            "from PyPI"
        )
        r = requests.get(
            f"https://pypi.org/pypi/{package_name_with_case}/json", timeout=(5, 30)
        )
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
