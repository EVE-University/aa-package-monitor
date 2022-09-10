from collections import namedtuple
from unittest import mock

import requests_mock
from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.core import (
    compile_package_requirements,
    gather_distribution_packages,
    update_packages_from_pypi,
)

from .factories import (
    DistributionPackageFactory,
    DjangoAppConfigStub,
    ImportlibDistributionStubFactory,
    PypiFactory,
    PypiReleaseFactory,
    distributions_to_packages,
)

MODULE_PATH = "package_monitor.core"

SysVersionInfo = namedtuple("SysVersionInfo", ["major", "minor", "micro"])


class TestDistributionPackage(NoSocketsTestCase):
    def test_should_not_be_editable(self):
        # given
        obj = DistributionPackageFactory()
        # when/then
        self.assertFalse(obj.is_editable())

    @mock.patch(MODULE_PATH + ".os.path.isfile")
    def test_should_be_editable(self, mock_isfile):
        # given
        mock_isfile.return_value = True
        obj = DistributionPackageFactory()
        # when/then
        self.assertTrue(obj.is_editable())


@mock.patch(MODULE_PATH + ".importlib_metadata.distributions", spec=True)
class TestFetchRelevantPackages(NoSocketsTestCase):
    def test_should_fetch_all_packages(self, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha")
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        distributions = lambda: iter([dist_alpha, dist_bravo])  # noqa: E731
        packages = distributions_to_packages(distributions())
        mock_distributions.side_effect = distributions
        # when
        result = gather_distribution_packages()
        # then
        self.assertSetEqual(set(packages.keys()), set(result.keys()))

    @mock.patch(MODULE_PATH + ".django_apps", spec=True)
    def test_should_detect_django_apps(self, mock_django_apps, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(
            name="alpha", files=["alpha/__init__.py"]
        )
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        mock_distributions.side_effect = distributions
        mock_django_apps.get_app_configs.return_value = [
            DjangoAppConfigStub("alpha_app", "/alpha/__init__.py")
        ]
        # when
        result = gather_distribution_packages()
        # then
        package_alpha = result["alpha"]
        self.assertEqual(package_alpha.apps, ["alpha_app"])


@mock.patch(MODULE_PATH + ".importlib_metadata.distributions", spec=True)
class TestCompilePackageRequirements(NoSocketsTestCase):
    def test_should_compile_requirements(self, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha")
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        distributions = lambda: iter([dist_alpha, dist_bravo])  # noqa: E731
        packages = distributions_to_packages(distributions())
        mock_distributions.side_effect = distributions
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_requirements(self, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha")
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        dist_charlie = ImportlibDistributionStubFactory(
            name="charlie", requires=["2009r"]
        )
        distributions = lambda: iter(  # noqa: E731
            [dist_alpha, dist_bravo, dist_charlie]
        )
        packages = distributions_to_packages(distributions())
        mock_distributions.side_effect = distributions
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_python_version_requirements(self, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha")
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        dist_charlie = ImportlibDistributionStubFactory(
            name="charlie", requires=["alpha>=1.0.0;python_version<3.7"]
        )
        distributions = lambda: iter(  # noqa: E731
            [dist_alpha, dist_bravo, dist_charlie]
        )
        packages = distributions_to_packages(distributions())
        mock_distributions.side_effect = distributions
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_extra_requirements(self, mock_distributions):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha")
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        dist_charlie = ImportlibDistributionStubFactory(
            name="charlie", requires=['alpha>=1.0.0; extra == "certs"']
        )
        distributions = lambda: iter(  # noqa: E731
            [dist_alpha, dist_bravo, dist_charlie]
        )
        packages = distributions_to_packages(distributions())
        mock_distributions.side_effect = distributions
        # when
        result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)


@requests_mock.Mocker()
class TestUpdatePackagesFromPyPi(NoSocketsTestCase):
    def test_should_update_packages(self, requests_mocker):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
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

    def test_should_ignore_prereleases_when_stable(self, requests_mocker):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
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
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0a1")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
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
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
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
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
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
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
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
