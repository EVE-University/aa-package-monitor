from collections import namedtuple
import json

from importlib_metadata import distributions

from packaging.version import Version as Pep440Version
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
import requests

from django.apps import apps as django_apps
from django.db import models, transaction


Distributions = namedtuple("Distributions", ["name", "files", "distribution"])


class DistributionManager(models.Manager):
    def update_all(self):
        my_distributions = [
            Distributions(
                name=dist.metadata["Name"].lower(),
                distribution=dist,
                files=[
                    "/" + str(f) for f in dist.files if str(f).endswith("__init__.py")
                ],
            )
            for dist in distributions()
        ]

        packages = dict()
        for dist in my_distributions:
            for app in django_apps.get_app_configs():
                my_file = app.module.__file__
                for dist_file in dist.files:
                    if my_file.endswith(dist_file):
                        if dist.name not in packages:
                            requirements = (
                                [Requirement(r) for r in dist.distribution.requires]
                                if dist.distribution.requires
                                else list()
                            )
                            packages[dist.name] = {
                                "name": dist.name,
                                "apps": list(),
                                "current": Pep440Version(dist.distribution.version),
                                "requirements": requirements,
                                "distribution": dist.distribution,
                            }

                        packages[dist.name]["apps"].append(app.name)
                        break

        requirements = dict()
        for package_name, package in packages.items():
            for requirement in package["requirements"]:
                requirement_name = requirement.name.lower()
                if requirement.specifier and requirement_name in packages:
                    if requirement_name not in requirements:
                        requirements[requirement_name] = SpecifierSet()

                    requirements[requirement_name] &= requirement.specifier

        for package_name in packages:
            r = requests.get(f"https://pypi.org/pypi/{package_name}/json")
            if r.status_code == requests.codes.ok:
                pypi_info = r.json()
                latest = None
                for release, _ in pypi_info["releases"].items():
                    my_release = Pep440Version(release)
                    if not my_release.is_prerelease:
                        if package_name in requirements:
                            is_valid = my_release in requirements[package_name]
                        else:
                            is_valid = True

                        if is_valid and (not latest or my_release > latest):
                            latest = my_release

            else:
                latest = None

            packages[package_name]["latest"] = latest

        with transaction.atomic():
            self.all().delete()
            for package in packages.values():
                is_outdated = (
                    package["current"] < package["latest"]
                    if package["latest"]
                    else None
                )
                description = (
                    package["distribution"].metadata["Summary"]
                    if package["distribution"].metadata["Summary"] != "UNKNOWN"
                    else ""
                )
                website_url = (
                    package["distribution"].metadata["Home-page"]
                    if package["distribution"].metadata["Home-page"] != "UNKNOWN"
                    else ""
                )
                self.create(
                    name=package["name"],
                    apps=json.dumps(package["apps"]),
                    installed_version=str(package["current"]),
                    latest_version=str(package["latest"]) if package["latest"] else "",
                    is_outdated=is_outdated,
                    description=description,
                    website_url=website_url,
                )
