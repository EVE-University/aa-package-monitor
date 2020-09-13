import json
import re
from unittest.mock import patch, Mock

from importlib_metadata import PackagePath
from packaging.specifiers import SpecifierSet
from packaging.version import Version as Pep440Version, LegacyVersion
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
            requires=["dummy-1<0.3.0"],
        ),
        ImportlibDistributionStub(
            name="dummy-3",
            version="0.3.0",
            files=["dummy_3/file_3.py", "dummy_3/__init__.py"],
            requires=["dummy-1>0.1.0"],
        ),
        ImportlibDistributionStub(
            name="dummy-4",
            version="0.4.0",
            files=["dummy_4/file_4.py"],
        ),
        ImportlibDistributionStub(
            name="dummy-5",
            version="0.5.0",
            files=["dummy_5/file_5.py"],
        ),
    ]


def get_app_configs_stub():
    return [
        DjangoAppConfigStub("dummy_1", "/dummy_1/__init__.py"),
        DjangoAppConfigStub("dummy_2a", "/dummy_2a/__init__.py"),
        DjangoAppConfigStub("dummy_2b", "/dummy_2b/__init__.py"),
    ]


@patch(MODULE_PATH_MANAGERS + ".django_apps", spec=True)
@patch(MODULE_PATH_MANAGERS + ".distributions", spec=True)
class TestSelectRelevantPackages(NoSocketsTestCase):
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False)
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", None)
    def test_default(self, mock_distributions, mock_django_apps):
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub

        result = Distribution.objects._select_relevant_packages()

        self.assertSetEqual(set(result.keys()), {"dummy-1", "dummy-2"})
        self.assertEqual(result["dummy-1"]["name"], "dummy-1")
        self.assertSetEqual(set(result["dummy-1"]["apps"]), {"dummy_1"})
        self.assertEqual(result["dummy-1"]["current"], Pep440Version("0.1.0"))
        d1_raw = distributions_stub()[0]
        self.assertEqual(
            result["dummy-1"]["distribution"].metadata["Name"], d1_raw.metadata["Name"]
        )

        # multiple apps belonging to the same package
        self.assertEqual(result["dummy-2"]["name"], "dummy-2")
        self.assertSetEqual(set(result["dummy-2"]["apps"]), {"dummy_2a", "dummy_2b"})

    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False)
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", ["dummy-4"])
    def test_include_packages(self, mock_distributions, mock_django_apps):
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub

        result = Distribution.objects._select_relevant_packages()

        self.assertSetEqual(set(result.keys()), {"dummy-1", "dummy-2", "dummy-4"})

    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", None)
    def test_all_pages(self, mock_distributions, mock_django_apps):
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub

        result = Distribution.objects._select_relevant_packages()

        self.assertSetEqual(
            set(result.keys()), {"dummy-1", "dummy-2", "dummy-3", "dummy-4", "dummy-5"}
        )


class TestDistributionsUpdateAll(NoSocketsTestCase):
    @patch(MODULE_PATH_MANAGERS + ".distributions", spec=True)
    def test_distribution_packages_amended(self, mock_distributions):
        mock_distributions.side_effect = distributions_stub

        result = Distribution.objects._distribution_packages_amended()
        self.assertEqual(len(result), 5)
        d1 = result[0]
        d1_raw = distributions_stub()[0]
        self.assertEqual(d1.name, "dummy-1")
        self.assertEqual(d1.distribution.metadata["Name"], d1_raw.metadata["Name"])
        self.assertListEqual(d1.files, ["/dummy_1/__init__.py"])

    @patch(MODULE_PATH_MANAGERS + ".distributions", spec=True)
    def test_compile_package_requirements(self, mock_distributions):
        mock_distributions.side_effect = distributions_stub

        packages = {"alpha-1": [], "dummy-1": []}
        result = Distribution.objects._compile_package_requirements(packages)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result["dummy-1"]["specifier"],
            SpecifierSet("<0.3.0") & SpecifierSet(">0.1.0"),
        )
        self.assertEqual(set(result["dummy-1"]["used_by"]), {"dummy-2", "dummy-3"})

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
            "dummy-2": {
                "name": "dummy-2",
                "current": Pep440Version("0.2.1"),
                "latest": Pep440Version("0.3.0"),
                "apps": [],
                "distribution": ImportlibDistributionStub(
                    "dummy-2",
                    "0.2.1",
                    list("xyz"),
                    homepage_url="homepage-dummy-2",
                    description="description-dummy-2",
                ),
            },
        }
        requirements = {
            "dummy-1": {
                "specifier": SpecifierSet("<0.3.0"),
                "used_by": ["dummy-3", "dummy-2"],
            }
        }
        Distribution.objects._save_packages(packages, requirements)
        dist = Distribution.objects.get(name="dummy-1")
        self.assertEqual(dist.name, "dummy-1")
        self.assertEqual(dist.apps, json.dumps(["dummy_1"]))
        self.assertEqual(
            dist.used_by,
            json.dumps(
                [
                    {"name": "dummy-2", "homepage_url": "homepage-dummy-2"},
                    {"name": "dummy-3", "homepage_url": ""},
                ]
            ),
        )
        self.assertEqual(dist.installed_version, "0.1.1")
        self.assertEqual(dist.latest_version, "0.2.0")
        self.assertTrue(dist.is_outdated)
        self.assertEqual(dist.website_url, "homepage-dummy-1")
        self.assertEqual(dist.description, "description-dummy-1")


pypi_info = {
    "dummy-1": {
        "info": None,
        "last_serial": "12345",
        "releases": {
            "0.1.0": ["dummy"],
            "0.2.0": ["dummy"],
            "0.3.0": ["dummy"],
        },
        "urls": None,
    },
    "legacy-1": {
        "info": None,
        "last_serial": "22345",
        "releases": {
            "2004d": ["dummy"],
        },
        "urls": None,
    },
}


def requests_get_stub(*args, **kwargs):
    r = Mock(spec=requests.Response)
    match = re.search(r"https:\/\/pypi\.org\/pypi\/(.+)\/json", args[0])
    name = match.group(1) if match else "(not found)"
    try:
        r.json.return_value = pypi_info[name]
    except KeyError:
        r.status_code = 404
    else:
        r.status_code = 200
    return r


@patch(MODULE_PATH_MANAGERS + ".requests", auto_spec=True)
class TestFetchVersionsFromPypi(NoSocketsTestCase):
    def test_normal(self, mock_requests):
        mock_requests.get.side_effect = requests_get_stub
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
        requirements = {"dummy-1": {"specifier": SpecifierSet("<0.3.0")}}
        Distribution.objects._fetch_versions_from_pypi(packages, requirements)
        self.assertEqual(packages["dummy-1"]["latest"], Pep440Version("0.2.0"))

    def test_can_handle_invalid_version(self, mock_requests):
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        packages = {
            "legacy-1": {
                "name": "legacy-1",
            },
        }
        Distribution.objects._fetch_versions_from_pypi(packages, dict())
        self.assertEqual(packages["legacy-1"]["latest"], LegacyVersion("2004d"))
