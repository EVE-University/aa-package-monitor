"""Module schedule calculates events for the update notification schedule."""

import datetime as dt
from typing import Optional

import pytz
from dateutil import rrule
from recurrent.event_parser import RecurringEvent

from django.utils.timezone import now


def is_notification_due(
    schedule_text: str, max_delay: int, last_report: Optional[dt.datetime]
) -> bool:
    """Reports whether a new update notification is due.

    Args:
        - schedule_text: Frequency in natural language
        - max_delay: how much seconds can pass after the scheduled event to still fire
        - last_report: Date of the last report or None
    """
    if not schedule_text:
        return True
    r = RecurringEvent()
    r.parse(schedule_text)
    now_2 = _aware2native(now())
    # occurrences needs to start way in the past
    # so we can always determine the previous occurrence
    r.dtstart = now_2 - dt.timedelta(days=30 * 6)
    rule = rrule.rrulestr(r.get_RFC_rrule())
    previous = rule.before(now_2)
    previous_latest = previous + dt.timedelta(seconds=max_delay)
    if last_report:
        last_report_2 = _aware2native(last_report)
        if previous <= last_report_2 <= previous_latest:
            return False
    return previous <= now_2 <= previous_latest


def _aware2native(d: dt.datetime) -> dt.datetime:
    return d.astimezone(pytz.utc).replace(tzinfo=None)
