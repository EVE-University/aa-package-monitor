"""Fetch information about distribution packages from PyPI."""

import concurrent.futures
import sys
from typing import Dict, Optional

import requests
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from packaging.version import parse as version_parse

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from package_monitor import __title__
from package_monitor.core.distribution_packages import DistributionPackage

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

# max workers used when fetching info from PyPI via UI
MAX_THREAD_WORKERS = 30


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

        latest, pypi_url = determine_latest_version(current_package, requirements)
        current_package.latest = latest
        current_package.homepage_url = pypi_url

    if use_threads:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        ) as executor:
            executor.map(thread_update_latest_from_pypi, packages.values())
    else:
        for package in packages.values():
            thread_update_latest_from_pypi(package)


def determine_latest_version(package: DistributionPackage, requirements: dict) -> str:
    """Determine latest version of a distribution package on PyPI."""

    pypi_data = _fetch_data_from_pypi(package)
    if not pypi_data:
        return "", ""

    consolidated_requirements = package.calc_consolidated_requirements(requirements)
    current_python_version = _current_python_version()
    latest = ""
    for release, release_details in pypi_data["releases"].items():
        requires_python = ""
        try:
            release_detail = release_details[-1] if len(release_details) > 0 else None
            if release_detail:
                if release_detail["yanked"]:
                    continue
                if (
                    requires_python := release_detail.get("requires_python")
                ) and current_python_version not in SpecifierSet(requires_python):
                    continue

            my_release = version_parse(release)
            if str(my_release) == str(release) and (
                package.is_prerelease() or not my_release.is_prerelease
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
                package.name,
                release,
            )
        except InvalidSpecifier:
            logger.info(
                "%s: Ignoring release with invalid requires_python: %s",
                package.name,
                requires_python,
            )

    if not latest:
        logger.warning(
            f"Could not find a release of '{package.name}' "
            f"that matches all requirements: '{consolidated_requirements}''"
        )

    pypi_url = _extract_pypi_url(pypi_data)
    return latest, pypi_url


def _fetch_data_from_pypi(package: DistributionPackage) -> Optional[dict]:
    """Fetch data for a package from PyPI."""

    logger.info(f"Fetching info for distribution package '{package.name}' from PyPI")

    url = f"https://pypi.org/pypi/{package.name}/json"
    r = requests.get(url, timeout=(5, 30))
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


def _current_python_version() -> Version:
    current_python_version = version_parse(
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}"
    )
    return current_python_version


def _extract_pypi_url(pypi_data) -> str:
    pypi_info = pypi_data.get("info")
    return pypi_info.get("project_url", "") if pypi_info else ""
