from app_utils.testing import NoSocketsTestCase

from .factories import DistributionFactory


class TestDistribution(NoSocketsTestCase):
    def test_should_update_has_installed_apps_1(self):
        # given
        obj = DistributionFactory()
        # when
        obj.calc_has_installed_apps()
        # then
        self.assertFalse(obj.has_installed_apps)

    def test_should_update_has_installed_apps_2(self):
        # given
        obj = DistributionFactory(apps=["dummy"])
        # when
        obj.calc_has_installed_apps()
        # then
        self.assertTrue(obj.has_installed_apps)

    def test_should_update_has_installed_apps_when_saved_1(self):
        # when
        obj = DistributionFactory()
        # then
        self.assertFalse(obj.has_installed_apps)

    def test_should_update_has_installed_apps_when_saved_2(self):
        # when
        obj = DistributionFactory(apps=["dummy"])
        # then
        self.assertTrue(obj.has_installed_apps)
