"""Helpers to deal with the importlib metadata library."""

import json
import os
import sys
from typing import List, Optional

from importlib_metadata import Distribution as MetadataDistribution
from packaging.requirements import InvalidRequirement, Requirement

from django.apps import apps as django_apps


def is_distribution_editable(dist: MetadataDistribution) -> bool:
    """Determine if a distribution is an editable install?"""
    # method for new packages conforming with pep 660
    direct_url_json = dist.read_text("direct_url.json")
    if direct_url_json:
        direct_url = json.loads(direct_url_json)
        if "dir_info" in direct_url and direct_url["dir_info"].get("editable") is True:
            return True

    # method for old packages
    for path_item in sys.path:
        egg_link = os.path.join(path_item, dist.name + ".egg-link")
        if os.path.isfile(egg_link):
            return True

    return False


def identify_installed_django_apps(dist: MetadataDistribution) -> List[str]:
    """Identify installed Django apps in metadata distribution
    and return their app labels.
    """
    if not dist.files:
        return []
    if "apps.py" not in {path.name for path in dist.files}:
        return []
    found_apps = []
    for dist_file in _extract_files(dist, pattern="__init__.py"):
        for app in django_apps.get_app_configs():
            if not app.module:
                continue
            my_file = app.module.__file__
            if my_file and my_file.endswith(dist_file):
                found_apps.append(app.name)
                break
    return found_apps


def _extract_files(dist: Optional[MetadataDistribution], pattern: str) -> List[str]:
    """Extract file paths from a distribution which filename match a pattern."""
    if not dist or not dist.files:
        return []
    dist_files = [str(f) for f in dist.files if f.name == pattern]
    return dist_files


# def _determine_homepage_url(dist: MetadataDistribution) -> str:
#     if url := dist_metadata_value(dist, "Home-page"):
#         return url
#     values = dist.metadata.get_all("Project-URL")
#     while values:
#         k, v = [o.strip() for o in values.pop(0).split(",")]
#         if k.lower() == "homepage":
#             return v
#     return ""


def parse_requirements(dist: MetadataDistribution) -> List[Requirement]:
    """Parse requirements from a distribution and return them.
    Invalid requirements will be ignored.
    """
    if not dist.requires:
        return []
    requirements = []
    for requirement in dist.requires:
        try:
            requirements.append(Requirement(requirement))
        except InvalidRequirement:
            pass
    return requirements


def metadata_value(dist: MetadataDistribution, prop: str) -> str:
    """Metadata value from distribution or empty string.
    Note: metadata can contain multiple values for the same key.
    This method will return the first only!
    """
    if dist and (value := dist.metadata.get(prop)) and value != "UNKNOWN":
        return value
    return ""
