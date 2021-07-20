from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

PACKAGE_PATH = "package_monitor.management.commands"


@patch(PACKAGE_PATH + ".package_monitor_refresh.Distribution.objects.update_all")
class TestPurgeAll(NoSocketsTestCase):
    def test_can_purge_all_data(self, mock_update_all):
        mock_update_all.return_value = 0

        out = StringIO()
        call_command("package_monitor_refresh", stdout=out)
        self.assertTrue(mock_update_all.called)
