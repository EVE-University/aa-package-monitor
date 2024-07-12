import datetime as dt
from collections import namedtuple
from unittest.mock import patch

from django.test import TestCase

from package_monitor.core.schedule import is_notification_due

MODULE_PATH = "package_monitor.core.schedule"

UTC = dt.timezone.utc


class TestSchedule(TestCase):
    def test_should_report_due_when_due(self):
        X = namedtuple(
            "X", ["schedule_text", "max_delay", "last_report", "now", "result"]
        )
        cases = [
            X(
                schedule_text="every day at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 10, 10, 0, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 10, 0, 1, tzinfo=UTC),
                result=True,
            ),
            X(
                schedule_text="every day at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 10, 5, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 10, 0, 1, tzinfo=UTC),
                result=False,
            ),
            X(
                schedule_text="every day at 10:00",
                max_delay=5400,
                last_report=None,
                now=dt.datetime(2024, 7, 11, 10, 0, 1, tzinfo=UTC),
                result=True,
            ),
            X(
                schedule_text="",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 10, 5, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 10, 0, 1, tzinfo=UTC),
                result=True,
            ),
            X(
                schedule_text="every thursday at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 6, 10, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 10, 0, 1, tzinfo=UTC),
                result=True,
            ),
            X(
                schedule_text="every thursday at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 10, 10, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 10, 0, 1, tzinfo=UTC),
                result=False,
            ),
            X(
                schedule_text="every thursday at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 9, 0, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 10, 1, 0, tzinfo=UTC),
                result=True,
            ),
            X(
                schedule_text="every thursday at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 9, 0, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 11, 31, 0, tzinfo=UTC),
                result=False,
            ),
            X(
                schedule_text="every thursday at 10:00",
                max_delay=5400,
                last_report=dt.datetime(2024, 7, 11, 9, 0, 0, tzinfo=UTC),
                now=dt.datetime(2024, 7, 11, 9, 59, 0, tzinfo=UTC),
                result=False,
            ),
        ]
        for num, tc in enumerate(cases, start=1):
            with self.subTest(num=num):
                with patch(MODULE_PATH + ".now") as m:
                    m.return_value = tc.now
                    x = is_notification_due(
                        schedule_text=tc.schedule_text,
                        max_delay=tc.max_delay,
                        last_report=tc.last_report,
                    )
                self.assertIs(x, tc.result)
