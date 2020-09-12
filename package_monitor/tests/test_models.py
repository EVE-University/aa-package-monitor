import json
from unittest.mock import patch, Mock

from importlib_metadata import PackagePath
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version as Pep440Version
import requests

from ..models import Distribution
from ..utils import NoSocketsTestCase

MODULE_PATH_MODELS = "package_monitor.models"
MODULE_PATH_MANAGERS = "package_monitor.managers"


class ImportlibDistributionStub:
    def __init__(
        self,
        name: str,
        version: str,
        files: list,
        requires: list = None,
        homepage_url: str = None,
        description: str = None,
    ) -> None:
        self.metadata = {
            "Name": name,
            "Home-page": homepage_url
            if homepage_url
            else f"http://www.example.com/{name.lower()}",
            "Summary": description if description else "",
        }
        self.version = version
        self.files = [PackagePath(f) for f in files]
        self.requires = requires if requires else None


class DjangoAppConfigStub:
    class ModuleStub:
        def __init__(self, file: str) -> None:
            self.__file__ = file

    def __init__(self, name: str, file: str) -> None:
        self.name = name
        self.module = self.ModuleStub(file)


class TestDistributionsUpdateAll(NoSocketsTestCase):
    @staticmethod
    def distributions_stub():
        return [
            ImportlibDistributionStub(
                name="Dummy-1",
                version="0.1.0",
                files=["dummy_1/file_1.py", "dummy_1/__init__.py"],
            ),
            ImportlibDistributionStub(
                name="dummy-2",
                version="0.2.0",
                files=[
                    "dummy_2/file_2.py",
                    "dummy_2a/__init__.py",
                    "dummy_2b/__init__.py",
                ],
                requires=["dummy-1<0.2.0"],
            ),
            ImportlibDistributionStub(
                name="dummy-3",
                version="0.3.0",
                files=["dummy_3/file_3.py", "dummy_3/__init__.py"],
                requires=["dummy-1<0.1.5"],
            ),
        ]

    @staticmethod
    def django_apps_stub():
        return

    @patch(MODULE_PATH_MANAGERS + ".distributions", spec=True)
    def test_distribution_packages_amended(self, mock_distributions):
        mock_distributions.side_effect = self.distributions_stub

        result = Distribution.objects._distribution_packages_amended()
        self.assertEqual(len(result), 3)
        d1 = result[0]
        d1_raw = self.distributions_stub()[0]
        self.assertEqual(d1.name, "dummy-1")
        self.assertEqual(d1.distribution.metadata["Name"], d1_raw.metadata["Name"])
        self.assertListEqual(d1.files, ["/dummy_1/__init__.py"])

    @patch(MODULE_PATH_MANAGERS + ".django_apps", spec=True)
    @patch(MODULE_PATH_MANAGERS + ".distributions", spec=True)
    def test_select_relevant_packages(self, mock_distributions, mock_django_apps):
        mock_distributions.side_effect = self.distributions_stub
        mock_django_apps.get_app_configs.return_value = [
            DjangoAppConfigStub("dummy_1", "/dummy_1/__init__.py"),
            DjangoAppConfigStub("dummy_2a", "/dummy_2a/__init__.py"),
            DjangoAppConfigStub("dummy_2b", "/dummy_2b/__init__.py"),
        ]

        result = Distribution.objects._select_relevant_packages()

        self.assertEqual(len(result), 2)
        self.assertEqual(result["dummy-1"]["name"], "dummy-1")
        self.assertSetEqual(set(result["dummy-1"]["apps"]), {"dummy_1"})
        self.assertEqual(result["dummy-1"]["current"], Pep440Version("0.1.0"))
        d1_raw = self.distributions_stub()[0]
        self.assertEqual(
            result["dummy-1"]["distribution"].metadata["Name"], d1_raw.metadata["Name"]
        )

        # multiple apps belonging to the same package
        self.assertEqual(result["dummy-2"]["name"], "dummy-2")
        self.assertSetEqual(set(result["dummy-2"]["apps"]), {"dummy_2a", "dummy_2b"})

    def test_compile_package_requirements(self):
        packages = {
            "alpha-1": {
                "name": "alpha-1",
                "requirements": [Requirement("dummy-1<0.2.0")],
            },
            "alpha-2": {
                "name": "alpha-2",
                "requirements": [Requirement("dummy-1>0.1.0")],
            },
            "dummy-1": {
                "name": "dummy-1",
                "requirements": [],
            },
        }
        result = Distribution.objects._compile_package_requirements(packages)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result["dummy-1"],
            SpecifierSet("<0.2.0") & SpecifierSet(">0.1.0"),
        )

    @patch(MODULE_PATH_MANAGERS + ".requests", auto_spec=True)
    def test_fetch_versions_from_pypi(self, mock_requests):
        def my_requests_get(*args, **kwargs):
            r = Mock(spec=requests.Response)
            r.json.return_value = {
                "info": None,
                "last_serial": "12345",
                "releases": {
                    "0.1.0": ["dummy"],
                    "0.2.0": ["dummy"],
                    "0.3.0": ["dummy"],
                },
                "urls": None,
            }
            r.status_code = 200
            return r

        mock_requests.get.side_effect = my_requests_get
        mock_requests.codes.ok = 200

        packages = {
            "alpha-1": {
                "name": "alpha-1",
            },
            "alpha-2": {
                "name": "alpha-2",
            },
            "dummy-1": {
                "name": "dummy-1",
                "current": "0.1.1",
                "requirements": [],
            },
        }
        requirements = {"dummy-1": SpecifierSet("<0.3.0")}
        Distribution.objects._fetch_versions_from_pypi(packages, requirements)
        self.assertEqual(packages["dummy-1"]["latest"], Pep440Version("0.2.0"))

    def test_save_packages(self):
        packages = {
            "dummy-1": {
                "name": "dummy-1",
                "current": Pep440Version("0.1.1"),
                "latest": Pep440Version("0.2.0"),
                "apps": ["dummy_1"],
                "distribution": ImportlibDistributionStub(
                    "dummy-1",
                    "0.1.0",
                    list("xyz"),
                    homepage_url="homepage-dummy-1",
                    description="description-dummy-1",
                ),
            },
        }
        Distribution.objects._save_packages(packages)
        dist = Distribution.objects.first()
        self.assertEqual(dist.name, "dummy-1")
        self.assertEqual(dist.apps, json.dumps(["dummy_1"]))
        self.assertEqual(dist.installed_version, "0.1.1")
        self.assertEqual(dist.latest_version, "0.2.0")
        self.assertTrue(dist.is_outdated)
        self.assertEqual(dist.website_url, "homepage-dummy-1")
        self.assertEqual(dist.description, "description-dummy-1")
