from app_utils.testing import NoSocketsTestCase

from .factories import DistributionFactory


class TestDistribution(NoSocketsTestCase):
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

    def test_should_not_be_outdated(self):
        # given
        obj = DistributionFactory(installed_version="1.0.0", latest_version="1.0.0")
        # when/then
        self.assertFalse(obj.calc_is_outdated())
        self.assertFalse(obj.is_outdated)

    def test_should_be_outdated(self):
        # given
        obj = DistributionFactory(installed_version="1.0.0", latest_version="1.1.0")
        # when/then
        self.assertTrue(obj.calc_is_outdated())
        self.assertTrue(obj.is_outdated)

    def test_should_return_none_as_outdated(self):
        # given
        obj = DistributionFactory(installed_version="1.0.0", latest_version="")
        # when/then
        self.assertIsNone(obj.calc_is_outdated())
        self.assertIsNone(obj.is_outdated)
