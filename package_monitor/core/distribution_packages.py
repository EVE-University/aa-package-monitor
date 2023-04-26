"""Handle parsed distribution packages."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import importlib_metadata
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import parse as version_parse

from . import metadata_helpers


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
