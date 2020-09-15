import json
import re
from unittest.mock import patch, Mock

from importlib_metadata import PackagePath
import requests

from ..models import Distribution
from .testdata import create_testdata
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
            "Home-page": homepage_url if homepage_url else "UNKNOWN",
            "Summary": description if description else "UNKNOWN",
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
            name="dummy-1",
            version="0.1.1",
            files=["dummy_1/file_1.py", "dummy_1/__init__.py"],
            homepage_url="homepage-dummy-1",
            description="description-dummy-1",
        ),
        ImportlibDistributionStub(
            name="Dummy-2",
            version="0.2.0",
            files=[
                "dummy_2/file_2.py",
                "dummy_2a/__init__.py",
                "dummy_2b/__init__.py",
            ],
            requires=["dummy-1<0.3.0", "dummy-3<0.4.0;python_version<3.5"],
            homepage_url="homepage-dummy-2",
            description="package name starts with capital, dependency to Python version",
        ),
        ImportlibDistributionStub(
            name="dummy-3",
            version="0.3.0",
            files=["dummy_3/file_3.py", "dummy_3/__init__.py"],
            requires=["dummy-1>0.1.0", "dummy-4", 'dummy-2==0.1.0; extra == "certs"'],
            description="invalid extra requirement for dummy-2",
        ),
        ImportlibDistributionStub(
            name="dummy-4",
            version="1.0.0b2",
            files=["dummy_4/file_4.py"],
            description="only prereleases",
        ),
        ImportlibDistributionStub(
            name="dummy-5",
            version="2009r",
            files=["dummy_5/file_5.py"],
            description="Invalid version number",
        ),
    ]


def get_app_configs_stub():
    return [
        DjangoAppConfigStub("dummy_1", "/dummy_1/__init__.py"),
        DjangoAppConfigStub("dummy_2a", "/dummy_2a/__init__.py"),
        DjangoAppConfigStub("dummy_2b", "/dummy_2b/__init__.py"),
    ]


pypi_info = {
    "dummy-1": {
        "info": None,
        "last_serial": "112345",
        "releases": {
            "0.1.0": ["dummy"],
            "0.2.0": ["dummy"],
            "0.3.0b1": ["dummy"],
            "0.3.0": ["dummy"],
        },
        "urls": None,
    },
    "dummy-2": {
        "info": None,
        "last_serial": "212345",
        "releases": {
            "0.1.0": ["dummy"],
            "0.2.0": ["dummy"],
            "0.3.0": ["dummy"],
        },
        "urls": None,
    },
    "dummy-3": {
        "info": None,
        "last_serial": "312345",
        "releases": {
            "0.5.0": ["dummy"],
            "0.4.0": ["dummy"],
            "0.3.0": ["dummy"],
        },
        "urls": None,
    },
    "dummy-4": {
        "info": None,
        "last_serial": "512345",
        "releases": {
            "1.0.0b1": ["dummy"],
            "1.0.0b2": ["dummy"],
            "1.0.0b3": ["dummy"],
        },
        "urls": None,
    },
    "dummy-5": {
        "info": None,
        "last_serial": "512345",
        "releases": {
            "2010b": ["dummy"],
            "2010c": ["dummy"],
            "2010r": ["dummy"],
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
@patch(MODULE_PATH_MANAGERS + ".django_apps", spec=True)
@patch(MODULE_PATH_MANAGERS + ".distributions", spec=True)
class TestDistributionsUpdateAll(NoSocketsTestCase):
    def test_package_with_apps(
        self, mock_distributions, mock_django_apps, mock_requests
    ):
        """
        when a normal package with apps is processed
        then the resulting object contains a list of apps
        """
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        obj = Distribution.objects.get(name="dummy-1")
        self.assertEqual(obj.installed_version, "0.1.1")
        self.assertEqual(obj.latest_version, "0.2.0")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.apps, json.dumps(["dummy_1"]))
        self.assertTrue(obj.has_installed_apps)
        self.assertEqual(
            obj.used_by,
            json.dumps(
                [
                    {"name": "Dummy-2", "homepage_url": "homepage-dummy-2"},
                    {"name": "dummy-3", "homepage_url": ""},
                ]
            ),
        )
        self.assertEqual(obj.website_url, "homepage-dummy-1")
        self.assertEqual(obj.description, "description-dummy-1")

    def test_package_name_with_capitals(
        self, mock_distributions, mock_django_apps, mock_requests
    ):
        """
        when package name has capitals
        those are retained for the saved distribution object
        """
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        self.assertTrue(Distribution.objects.filter(name="Dummy-2").exists())

    def test_invalid_version(self, mock_distributions, mock_django_apps, mock_requests):
        """
        when current version can not be parsed
        then no latest_version wil be provided and is_outdated is set to None
        """
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        obj = Distribution.objects.get(name="dummy-5")
        self.assertEqual(obj.installed_version, "2009r")
        self.assertEqual(obj.latest_version, "")
        self.assertIsNone(obj.is_outdated)
        self.assertEqual(obj.apps, json.dumps([]))
        self.assertFalse(obj.has_installed_apps)
        self.assertEqual(obj.website_url, "")

    def test_handle_preleases_only(
        self, mock_distributions, mock_django_apps, mock_requests
    ):
        """
        when current is a pre release
        then latest can also be a (never) pre release
        """
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        obj = Distribution.objects.get(name="dummy-4")
        self.assertEqual(obj.installed_version, "1.0.0b2")
        self.assertEqual(obj.latest_version, "1.0.0b3")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.apps, json.dumps([]))
        self.assertFalse(obj.has_installed_apps)
        self.assertEqual(obj.website_url, "")

    def test_pypi_is_offline(self, mock_distributions, mock_django_apps, mock_requests):
        """
        when pypi is offline
        then last_version for all packages is empty and is_outdated is set to None
        """

        def requests_get_error_stub(*args, **kwargs):
            r = Mock(spec=requests.Response)
            r.status_code = 500
            return r

        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_error_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        obj = Distribution.objects.get(name="dummy-1")
        self.assertEqual(obj.latest_version, "")
        self.assertIsNone(obj.is_outdated)

    def test_invalid_extra_requirement(
        self, mock_distributions, mock_django_apps, mock_requests
    ):
        """
        when a package has an invalid extra requirement for another package
        then requirement is ignored
        """
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        obj = Distribution.objects.get(name="dummy-2")
        self.assertEqual(obj.installed_version, "0.2.0")
        self.assertEqual(obj.latest_version, "0.3.0")
        self.assertTrue(obj.is_outdated)

    def test_handle_python_requirement(
        self, mock_distributions, mock_django_apps, mock_requests
    ):
        """
        when x
        then y
        """
        mock_distributions.side_effect = distributions_stub
        mock_django_apps.get_app_configs.side_effect = get_app_configs_stub
        mock_requests.get.side_effect = requests_get_stub
        mock_requests.codes.ok = 200

        result = Distribution.objects.update_all()
        self.assertEqual(result, 5)

        obj = Distribution.objects.get(name="dummy-3")
        self.assertEqual(obj.installed_version, "0.3.0")
        self.assertEqual(obj.latest_version, "0.5.0")
        self.assertTrue(obj.is_outdated)


class TestCurrentlySelected(NoSocketsTestCase):
    def setUp(self) -> None:
        create_testdata()

    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", None)
    def test_all_packages(self):
        result = Distribution.objects.currently_selected()
        self.assertEqual(result.count(), 3)

    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False)
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", None)
    def test_apps_related_packages(self):
        result = Distribution.objects.currently_selected()
        self.assertEqual(result.count(), 1)
        self.assertEqual(set(result.values_list("name", flat=True)), {"dummy-1"})

    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False)
    @patch(MODULE_PATH_MANAGERS + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", ["dummy-3"])
    def test_apps_related_packages_plus_addons(self):
        result = Distribution.objects.currently_selected()
        self.assertEqual(result.count(), 2)
        self.assertEqual(
            set(result.values_list("name", flat=True)), {"dummy-1", "dummy-3"}
        )
