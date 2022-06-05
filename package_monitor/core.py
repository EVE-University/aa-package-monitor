from collections import namedtuple
from dataclasses import dataclass, field
from typing import Dict, List

import importlib_metadata
from importlib_metadata import distributions
from packaging.markers import UndefinedComparison, UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from django.apps import apps as django_apps

_DistributionInfo = namedtuple("_DistributionInfo", ["name", "files", "distribution"])


@dataclass
class DistributionPackage:
    name: str
    current: str
    distribution: importlib_metadata.Distribution
    requirements: List[Requirement] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    latest: str = ""


def select_relevant_packages() -> Dict[str, DistributionPackage]:
    """returns subset of distribution packages with packages of interest

    Interesting packages are related to installed apps or explicitely defined
    """
    packages = dict()
    for dist in _distribution_packages_amended():
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


def _distribution_packages_amended() -> list:
    """returns the list of all known distribution packages with amended infos"""
    return [
        _DistributionInfo(
            name=canonicalize_name(dist.metadata["Name"]),
            distribution=dist,
            files=["/" + str(f) for f in dist.files if str(f).endswith("__init__.py")],
        )
        for dist in distributions()
        if dist.metadata["Name"]
    ]


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


def compile_package_requirements(packages: dict) -> dict:
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
