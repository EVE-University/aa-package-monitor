from unittest import mock

import requests_mock
from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.core import compile_package_requirements, update_packages_from_pypi

from .factories import (
    DistributionPackageFactory,
    ImportlibDistributionStubFactory,
    PypiFactory,
    PypiReleaseFactory,
    distributions_to_packages,
)

MODULE_PATH = "package_monitor.core"


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


@requests_mock.Mocker()
class TestUpdatePackagesFromPyPi(NoSocketsTestCase):
    def test_should_update_packages(self, requests_mocker):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        packages = distributions_to_packages(distributions())
        requirements = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
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
