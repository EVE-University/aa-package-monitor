from unittest import mock

from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.models import Distribution

from .factories import (
    DistributionFactory,
    ImportlibDistributionStubFactory,
    distributions_to_packages,
)

MODULE_PATH = "package_monitor.managers"


@mock.patch(MODULE_PATH + ".update_packages_from_pypi", spec=True)
@mock.patch(MODULE_PATH + ".compile_package_requirements", spec=True)
@mock.patch(MODULE_PATH + ".fetch_relevant_packages", spec=True)
class TestDistributionsUpdateAll(NoSocketsTestCase):
    def test_should_create_new_packages_from_scratch(
        self,
        mock_fetch_relevant_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = ImportlibDistributionStubFactory(
            name="alpha",
            version="1.0.0",
            homepage_url="https://www.alpha.com",
            description="alpha-description",
        )
        dist_bravo = ImportlibDistributionStubFactory(
            name="bravo",
            requires=["alpha>=1.0.0"],
            homepage_url="https://www.bravo.com",
        )
        packages = distributions_to_packages([dist_alpha, dist_bravo])
        packages["alpha"].apps = ["alpha_app"]
        mock_fetch_relevant_packages.return_value = packages
        mock_compile_package_requirements.return_value = {
            "alpha": {"bravo": SpecifierSet(">=1.0.0")}
        }
        # when
        Distribution.objects.update_all(use_threads=False)
        # then
        self.assertEqual(Distribution.objects.count(), 2)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "1.0.0")
        self.assertFalse(obj.is_outdated)
        self.assertTrue(obj.has_installed_apps)
        self.assertEqual(obj.website_url, "https://www.alpha.com")
        self.assertEqual(obj.description, "alpha-description")
        self.assertListEqual(obj.apps, ["alpha_app"])
        self.assertEqual(
            obj.used_by,
            [
                {
                    "name": "bravo",
                    "homepage_url": "https://www.bravo.com",
                    "requirements": [">=1.0.0"],
                }
            ],
        )

    def test_should_retain_package_name_with_capitals(
        self,
        mock_fetch_relevant_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="Alpha", version="1.0.0")
        mock_fetch_relevant_packages.return_value = distributions_to_packages(
            [dist_alpha]
        )
        mock_compile_package_requirements.return_value = {}
        # when
        Distribution.objects.update_all(use_threads=False)
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.first()
        self.assertEqual(obj.name, "Alpha")
        self.assertEqual(obj.latest_version, "1.0.0")
        self.assertFalse(obj.is_outdated)

    def test_should_update_existing_packages(
        self,
        mock_fetch_relevant_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        mock_fetch_relevant_packages.return_value = distributions_to_packages(
            [dist_alpha]
        )
        mock_compile_package_requirements.return_value = {}
        DistributionFactory(name="alpha", installed_version="0.9.0")
        # when
        Distribution.objects.update_all(use_threads=False)
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "1.0.0")
        self.assertFalse(obj.is_outdated)

    def test_should_remove_stale_packages(
        self,
        mock_fetch_relevant_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="1.0.0")
        mock_fetch_relevant_packages.return_value = distributions_to_packages(
            [dist_alpha]
        )
        mock_compile_package_requirements.return_value = {}
        DistributionFactory(name="alpha", installed_version="0.9.0")
        DistributionFactory(name="bravo", installed_version="1.0.0")
        # when
        Distribution.objects.update_all(use_threads=False)
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "1.0.0")
        self.assertFalse(obj.is_outdated)

    def test_should_set_is_outdated_to_none_when_no_pypi_infos(
        self,
        mock_fetch_relevant_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = ImportlibDistributionStubFactory(name="alpha", version="")
        mock_fetch_relevant_packages.return_value = distributions_to_packages(
            [dist_alpha]
        )
        mock_compile_package_requirements.return_value = {}
        DistributionFactory(name="alpha", installed_version="0.9.0")
        # when
        Distribution.objects.update_all(use_threads=False)
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "")
        self.assertIsNone(obj.is_outdated)
