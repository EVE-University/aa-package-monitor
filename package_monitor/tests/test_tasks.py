from unittest.mock import patch

from django.test import TestCase

from .. import tasks

MODULE_PATH = "package_monitor.tasks"


@patch(MODULE_PATH + ".Distribution.objects.send_update_notifications")
@patch(MODULE_PATH + ".Distribution.objects.update_all")
class TestTasks(TestCase):
    def test_should_update_all_distributions_and_notify(
        self, update_all, send_update_notifications
    ):
        # when
        with patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", True):
            tasks.update_distributions()
        # then
        self.assertTrue(update_all.called)
        self.assertTrue(send_update_notifications.called)

    def test_should_update_all_distributions_and_not_notify(
        self, update_all, send_update_notifications
    ):
        # when
        with patch(MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED", False):
            tasks.update_distributions()
        # then
        self.assertTrue(update_all.called)
        self.assertFalse(send_update_notifications.called)
