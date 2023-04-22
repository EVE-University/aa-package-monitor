from unittest import mock

import requests_mock

from app_utils.testing import NoSocketsTestCase

from package_monitor import tasks
from package_monitor.core import DistributionPackage
from package_monitor.models import Distribution

from .factories import ImportlibDistributionStubFactory, PypiFactory, PypiReleaseFactory


@mock.patch("package_monitor.managers.PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False)
@mock.patch("package_monitor.core.django_apps", spec=True)
@mock.patch("package_monitor.core.importlib_metadata.distributions", spec=True)
@requests_mock.Mocker()
class TestUpdatePackagesFromPyPi(NoSocketsTestCase):
    def test_should_update_packages(
        self, mock_distributions, mock_django_apps, requests_mocker
    ):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        mock_distributions.side_effect = distributions
        mock_django_apps.get_app_configs.return_value = []
        pypi_alpha = PypiFactory(
            distribution=DistributionPackage.create_from_distribution(dist_alpha)
        )
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.register_uri(
            "GET", "https://pypi.org/pypi/alpha/json", json=pypi_alpha.asdict()
        )
        # when
        tasks.update_distributions()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "1.1.0")
