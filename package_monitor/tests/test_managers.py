from unittest import mock

from packaging.specifiers import SpecifierSet

from app_utils.testing import NoSocketsTestCase

from package_monitor.models import Distribution

from .factories import DistributionFactory, DistributionPackageFactory, make_packages

MODULE_PATH = "package_monitor.managers"


@mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False)
@mock.patch(MODULE_PATH + ".update_packages_from_pypi", spec=True)
@mock.patch(MODULE_PATH + ".compile_package_requirements", spec=True)
@mock.patch(MODULE_PATH + ".gather_distribution_packages", spec=True)
class TestDistributionsUpdateAll(NoSocketsTestCase):
    def test_should_create_new_packages_from_scratch(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="alpha",
            current="1.0.0",
            homepage_url="https://www.alpha.com",
            summary="alpha-description",
        )
        dist_bravo = DistributionPackageFactory(
            name="bravo",
            requires=["alpha>=1.0.0"],
            homepage_url="https://www.bravo.com",
        )
        packages = make_packages(dist_alpha, dist_bravo)
        packages["alpha"].apps = ["alpha_app"]
        mock_gather_distribution_packages.return_value = packages
        mock_compile_package_requirements.return_value = {
            "alpha": {"bravo": SpecifierSet(">=1.0.0")}
        }
        # when
        Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 2)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.installed_version, "1.0.0")
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
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="Alpha", current="1.0.0")
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.first()
        self.assertEqual(obj.name, "Alpha")
        self.assertEqual(obj.installed_version, "1.0.0")
        self.assertFalse(obj.is_outdated)

    def test_should_update_existing_packages(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        DistributionFactory(name="alpha", installed_version="0.9.0")
        # when
        Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.installed_version, "1.0.0")
        self.assertFalse(obj.is_outdated)

    def test_should_remove_stale_packages(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        DistributionFactory(name="alpha", installed_version="0.9.0")
        DistributionFactory(name="bravo", installed_version="1.0.0")
        # when
        Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.installed_version, "1.0.0")
        self.assertFalse(obj.is_outdated)

    def test_should_set_is_outdated_to_none_when_no_pypi_infos(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="")
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        DistributionFactory(name="alpha", installed_version="0.9.0")
        # when
        Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "")
        self.assertIsNone(obj.is_outdated)

    def test_should_set_is_outdated_to_none_when_current_version_can_not_be_parsed(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="2009r")
        packages = make_packages(dist_alpha)
        packages["alpha"].latest = ""
        mock_gather_distribution_packages.return_value = packages
        mock_compile_package_requirements.return_value = {}
        # when
        Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="alpha")
        self.assertEqual(obj.latest_version, "")
        self.assertIsNone(obj.is_outdated)


@mock.patch(MODULE_PATH + ".notify_admins", spec=True)
@mock.patch(MODULE_PATH + ".update_packages_from_pypi", spec=True)
@mock.patch(MODULE_PATH + ".compile_package_requirements", spec=True)
@mock.patch(MODULE_PATH + ".gather_distribution_packages", spec=True)
class TestDistributionsUpdateAllNotifications(NoSocketsTestCase):
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True)
    def test_should_notify_when_enabled_and_there_is_an_update(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
        mock_notify_admins,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="Alpha", current="1.0.0", latest="1.1.0"
        )
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True):
            Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="Alpha")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.latest_notified_version, "1.1.0")
        self.assertTrue(mock_notify_admins.called)

    def test_should_not_notify_when_disabled_via_setting(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
        mock_notify_admins,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="Alpha", current="1.0.0", latest="1.1.0"
        )
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False):
            Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="Alpha")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.latest_notified_version, "")
        self.assertFalse(mock_notify_admins.called)

    def test_should_notify_when_outdated_and_newer_update(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
        mock_notify_admins,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="Alpha", current="1.0.0", latest="1.1.0"
        )
        DistributionFactory(
            name="Alpha",
            installed_version="1.0.0",
            latest_version="1.1.0",
            is_outdated=True,
            latest_notified_version="1.0.0",
        )
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True):
            Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="Alpha")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.latest_notified_version, "1.1.0")
        self.assertTrue(mock_notify_admins.called)

    def test_should_not_notify_when_already_notified(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
        mock_notify_admins,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="Alpha", current="1.0.0", latest="1.1.0"
        )
        DistributionFactory(
            name="Alpha",
            installed_version="1.0.0",
            latest_version="1.1.0",
            is_outdated=True,
            latest_notified_version="1.1.0",
        )
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True):
            Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="Alpha")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.latest_notified_version, "1.1.0")
        self.assertFalse(mock_notify_admins.called)

    def test_should_not_notify_when_disabled_directly(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
        mock_notify_admins,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="Alpha", current="1.0.0", latest="1.1.0"
        )
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True):
            Distribution.objects.update_all(notifications_disabled=True)
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="Alpha")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.latest_notified_version, "")
        self.assertFalse(mock_notify_admins.called)

    def test_should_not_notify_when_editable_and_those_are_not_shown(
        self,
        mock_gather_distribution_packages,
        mock_compile_package_requirements,
        mock_update_packages_from_pypi,
        mock_notify_admins,
    ):
        # given
        dist_alpha = DistributionPackageFactory(
            name="Alpha", current="1.0.0", latest="1.1.0", is_editable=True
        )
        mock_gather_distribution_packages.return_value = make_packages(dist_alpha)
        mock_compile_package_requirements.return_value = {}
        # when
        with mock.patch(
            MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True
        ), mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False):
            Distribution.objects.update_all()
        # then
        self.assertEqual(Distribution.objects.count(), 1)
        obj = Distribution.objects.get(name="Alpha")
        self.assertTrue(obj.is_outdated)
        self.assertEqual(obj.latest_notified_version, "")
        self.assertFalse(mock_notify_admins.called)


class TestDistributionFilterVisible(NoSocketsTestCase):
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
    def test_should_have_all_packages(self):
        # given
        obj_1 = DistributionFactory()
        obj_2 = DistributionFactory()
        # when
        result = Distribution.objects.filter_visible()
        # then
        self.assertEqual(result.names(), {obj_1.name, obj_2.name})

    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
    def test_should_have_apps_only(self):
        # given
        obj_1 = DistributionFactory(apps=["app_1"])
        DistributionFactory()
        # when
        result = Distribution.objects.filter_visible()
        # then
        self.assertEqual(result.names(), {obj_1.name})

    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", ["include-me"])
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
    def test_should_have_apps_plus_included(self):
        # given
        obj_1 = DistributionFactory(apps=["app_1"])
        obj_2 = DistributionFactory(name="include-me")
        DistributionFactory()
        # when
        result = Distribution.objects.filter_visible()
        # then
        self.assertEqual(result.names(), {obj_1.name, obj_2.name})

    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", ["exclude-me"])
    def test_should_have_all_packages_minus_excluded(self):
        # given
        obj_1 = DistributionFactory()
        DistributionFactory(name="exclude-me")
        # when
        result = Distribution.objects.filter_visible()
        # then
        self.assertEqual(result.names(), {obj_1.name})

    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
    @mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
    def test_should_have_all_packages_minus_editable(self):
        # given
        obj_1 = DistributionFactory()
        DistributionFactory(name="exclude-me", is_editable=True)
        # when
        result = Distribution.objects.filter_visible()
        # then
        self.assertEqual(result.names(), {obj_1.name})


@mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_ALL_PACKAGES", True)
@mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES", False)
@mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_INCLUDE_PACKAGES", [])
@mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_EXCLUDE_PACKAGES", [])
class TestDistributionBuildInstallCommand(NoSocketsTestCase):
    def test_all_packages(self):
        # given
        DistributionFactory(name="alpha", latest_version="1.2.0")
        DistributionFactory(name="bravo", latest_version="2.1.0")
        # when
        result = Distribution.objects.order_by("name").build_install_command()
        # then
        self.assertEqual(result, "pip install alpha==1.2.0 bravo==2.1.0")

    def test_should_stay_within_max_line_length(self):
        # given
        DistributionFactory.create_batch(size=500)
        # when
        result = Distribution.objects.all().build_install_command()
        # then
        self.assertLessEqual(len(result), 4095)
