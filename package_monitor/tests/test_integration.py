from unittest import TestCase, mock

from aioresponses import aioresponses

from package_monitor import tasks
from package_monitor.core.distribution_packages import DistributionPackage
from package_monitor.models import Distribution

from .factories import MetadataDistributionStubFactory, PypiFactory, PypiReleaseFactory

CORE_PATH = "package_monitor.core.distribution_packages"
CORE_HELPERS_PATH = "package_monitor.core.metadata_helpers"
MANAGERS_PATH = "package_monitor.managers"


@mock.patch(MANAGERS_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False)
@mock.patch(CORE_HELPERS_PATH + ".django_apps", spec=True)
@mock.patch(CORE_PATH + ".importlib_metadata.distributions", spec=True)
class TestUpdatePackagesFromPyPi(TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        # workaround to remove obj which is not cleaned up
        Distribution.objects.all().delete()

    @aioresponses()
    def test_should_update_packages(
        self, mock_distributions, mock_django_apps, requests_mocker
    ):
        # given
        dist_alpha = MetadataDistributionStubFactory(name="alpha", version="1.0.0")
        distributions = lambda: iter([dist_alpha])  # noqa: E731
        mock_distributions.side_effect = distributions
        mock_django_apps.get_app_configs.return_value = []
        pypi_alpha = PypiFactory(
            distribution=DistributionPackage.create_from_metadata_distribution(
                dist_alpha
            )
        )
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        requests_mocker.get(
            "https://pypi.org/pypi/alpha/json", payload=pypi_alpha.asdict()
        )
        # when
        tasks.update_distributions()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "1.1.0")
