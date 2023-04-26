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


def pypi_api_url(project_name: str) -> str:
    """Generate PyPI API URL."""
    return f"https://pypi.org/pypi/{project_name}/json"


def update_packages_from_pypi(
    packages: Dict[str, DistributionPackage], requirements: dict, use_threads=False
) -> None:
    """Update packages with latest versions and URL from PyPI in accordance
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
            pypi_url = _fetch_pypi_url(pypi_data)
            latest = _determine_latest_version(current_package, requirements, pypi_data)
        else:
            latest, pypi_url = "", ""
        packages[package_name].latest = latest
        packages[package_name].homepage_url = pypi_url

    if use_threads:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        ) as executor:
            executor.map(thread_update_latest_from_pypi, packages.keys())
    else:
        for package_name in packages.keys():
            thread_update_latest_from_pypi(package_name)


def _fetch_data_from_pypi(package: DistributionPackage) -> Optional[dict]:
    """Fetch data for a package from PyPI."""

    logger.info(f"Fetching info for distribution package '{package.name}' from PyPI")

    url = pypi_api_url(package.name)
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


def _fetch_pypi_url(pypi_data) -> str:
    pypi_info = pypi_data.get("info")
    return pypi_info.get("project_url", "") if pypi_info else ""


def _determine_latest_version(
    package: DistributionPackage, requirements, pypi_data: dict
) -> str:
    """Determine latest version of a distribution package on PyPI."""
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
    return latest


def _current_python_version() -> Version:
    current_python_version = version_parse(
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}"
    )
    return current_python_version
