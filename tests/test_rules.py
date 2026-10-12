"""Правила напоминаний: чистые функции, без БД, без Tk, без часов реального времени."""

from datetime import UTC, datetime, timedelta

import pytest

from reminder.domain.models import ChangeStatus, Notify, Reminder, Reschedule, Status
from reminder.domain.rules import SNOOZE_DELAY, decide, snooze

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)
CATCH_UP = timedelta(minutes=5)


def make(due_at: datetime, *, status: Status = Status.WAITING, notified_at=None) -> Reminder:
    return Reminder(
        id=1,
        title="Позвонить врачу",
        description="",
        due_at=due_at,
        status=status,
        notified_at=notified_at,
    )


def test_future_reminder_produces_nothing():
    reminder = make(NOW + timedelta(minutes=1))

    assert decide([reminder], NOW, CATCH_UP) == []


def test_due_reminder_is_notified_and_marked_overdue():
    reminder = make(NOW - timedelta(seconds=30))

    assert decide([reminder], NOW, CATCH_UP) == [
        Notify(reminder),
        ChangeStatus(reminder.id, Status.OVERDUE),
    ]


def test_long_overdue_reminder_is_marked_without_notification():
    reminder = make(NOW - timedelta(hours=9))

    assert decide([reminder], NOW, CATCH_UP) == [ChangeStatus(reminder.id, Status.OVERDUE)]


def test_already_notified_reminder_is_only_marked():
    reminder = make(NOW - timedelta(seconds=30), notified_at=NOW - timedelta(seconds=30))

    assert decide([reminder], NOW, CATCH_UP) == [ChangeStatus(reminder.id, Status.OVERDUE)]


def test_decide_keeps_input_order_for_several_reminders():
    first = make(NOW - timedelta(hours=9))
    second = make(NOW - timedelta(seconds=30))

    assert decide([first, second], NOW, CATCH_UP) == [
        ChangeStatus(first.id, Status.OVERDUE),
        Notify(second),
        ChangeStatus(second.id, Status.OVERDUE),
    ]


def test_snooze_moves_due_date_by_thirty_minutes_by_default():
    reminder = make(NOW - timedelta(minutes=1), status=Status.OVERDUE)

    assert SNOOZE_DELAY == timedelta(minutes=30)
    assert snooze(reminder, NOW) == [Reschedule(reminder.id, NOW + timedelta(minutes=30))]


def test_snooze_accepts_custom_delay():
    reminder = make(NOW, status=Status.WAITING)

    assert snooze(reminder, NOW, timedelta(hours=2)) == [
        Reschedule(reminder.id, NOW + timedelta(hours=2))
    ]


@pytest.mark.parametrize("status", [Status.DONE, Status.CANCELLED])
def test_snooze_refuses_final_statuses(status):
    reminder = make(NOW, status=status)

    with pytest.raises(ValueError, match="конечн"):
        snooze(reminder, NOW)
