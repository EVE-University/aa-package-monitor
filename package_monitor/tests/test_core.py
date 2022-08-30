from unittest import mock

from app_utils.testing import NoSocketsTestCase

from .factories import DistributionPackageFactory

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
