from collections import namedtuple
from unittest import mock

from requests_mock import Mocker

from app_utils.testing import NoSocketsTestCase

from package_monitor.core.pypi import (
    _fetch_data_from_pypi,
    _fetch_pypi_url,
    update_packages_from_pypi,
)
from package_monitor.tests.factories import (
    DistributionPackageFactory,
    PypiFactory,
    PypiReleaseFactory,
    make_packages,
)

MODULE_PATH = "package_monitor.core.pypi"

SysVersionInfo = namedtuple("SysVersionInfo", ["major", "minor", "micro"])


@Mocker()
class TestUpdatePackagesFromPyPi(NoSocketsTestCase):
    def test_should_update_packages(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.1.0")
        self.assertEqual(
            packages["alpha"].homepage_url, "https://pypi.org/project/alpha/"
        )

    def test_should_ignore_prereleases_when_stable(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0a1"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    def test_should_include_prereleases_when_prerelease(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0a1")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.0.0a2"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0a2")

    def test_should_set_latest_to_empty_string_on_network_error(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET",
            "https://pypi.org/pypi/alpha/json",
            status_code=500,
            reason="Test error",
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "")

    def test_should_ignore_yanked_releases(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(yanked=True)]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    @mock.patch(MODULE_PATH + ".sys")
    def test_should_ignore_releases_with_incompatible_python_requirement(
        self, requests_mocker, mock_sys
    ):
        # given
        mock_sys.version_info = SysVersionInfo(3, 6, 9)
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.7")]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    def test_should_ignore_invalid_release_version(self, requests_mocker):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["a3"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        update_packages_from_pypi(
            packages=packages, requirements=requirements, use_threads=False
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")


@Mocker()
class TestFetchDataFromPypi(NoSocketsTestCase):
    def test_should_return_data(self, requests_mocker: Mocker):
        # given
        obj = DistributionPackageFactory(name="alpha")
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json={"alpha": 1}
        )
        # when
        result = _fetch_data_from_pypi(obj)
        # then
        self.assertEqual(result, {"alpha": 1})

    def test_should_return_none_when_package_does_not_exist(
        self, requests_mocker: Mocker
    ):
        # given
        obj = DistributionPackageFactory(name="alpha")
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", status_code=404
        )
        # when
        result = _fetch_data_from_pypi(obj)
        # then
        self.assertIsNone(result)

    def test_should_return_none_on_other_http_errors(self, requests_mocker: Mocker):
        # given
        obj = DistributionPackageFactory(name="alpha")
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", status_code=500
        )
        # when
        result = _fetch_data_from_pypi(obj)
        # then
        self.assertIsNone(result)


class TestFetchPypiUrl(NoSocketsTestCase):
    def test_should_return_url(self):
        # given
        distribution = DistributionPackageFactory(name="alpha")
        data = PypiFactory(distribution=distribution)
        # when
        result = _fetch_pypi_url(data.asdict())
        # then
        self.assertEqual(result, "https://pypi.org/project/alpha/")
