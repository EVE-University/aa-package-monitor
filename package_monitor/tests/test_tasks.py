from collections import namedtuple
from unittest.mock import patch

from django.test import TestCase, override_settings

from package_monitor import tasks

MODULE_PATH = "package_monitor.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateDistributions(TestCase):
    def test_should_update_all_distributions_and_notify(self):
        X = namedtuple(
            "X",
            [
                "should_notify",
                "notifications_enabled",
                "show_editable",
                "should_repeat",
            ],
        )
        cases = [
            X(True, True, False, False),
            X(False, False, False, False),
            X(True, True, True, False),
            X(True, True, False, True),
        ]
        for num, tc in enumerate(cases, 1):
            with self.subTest("test update distributions", num=num):
                with patch(
                    MODULE_PATH + ".PACKAGE_MONITOR_NOTIFICATIONS_ENABLED",
                    tc.notifications_enabled,
                ), patch(
                    MODULE_PATH + ".PACKAGE_MONITOR_SHOW_EDITABLE_PACKAGES",
                    tc.show_editable,
                ), patch(
                    MODULE_PATH + ".PACKAGE_MONITOR_REPEAT_NOTIFICATIONS",
                    tc.should_repeat,
                ), patch(
                    MODULE_PATH + ".Distribution.objects.send_update_notification",
                    spec=True,
                ) as send_update_notification, patch(
                    MODULE_PATH + ".Distribution.objects.update_all", spec=True
                ) as update_all:
                    tasks.update_distributions()

                self.assertTrue(update_all.called)
                self.assertIs(tc.should_notify, send_update_notification.called)
                if tc.should_notify:
                    _, kwargs = send_update_notification.call_args
                    self.assertIs(tc.show_editable, kwargs["show_editable"])
                    self.assertIs(tc.should_repeat, kwargs["should_repeat"])
