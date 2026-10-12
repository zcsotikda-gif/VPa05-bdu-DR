"""Очередь окна: уведомитель, который можно звать из фонового потока.

Окно Tk создаётся только в главном потоке, поэтому планировщик не рисует сам,
а кладёт напоминание в очередь. Эта часть проверяется без Tk и без экрана.
"""

from datetime import UTC, datetime

from reminder.domain.models import Reminder, Status
from reminder.notifications.popup import PopupQueueNotifier

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


def make(reminder_id: int = 1) -> Reminder:
    return Reminder(
        id=reminder_id,
        title="Позвонить врачу",
        description="",
        due_at=NOW,
        status=Status.WAITING,
        notified_at=None,
    )


def test_send_puts_reminder_into_queue_and_reports_success():
    notifier = PopupQueueNotifier()
    reminder = make()

    assert notifier.send(reminder) is True
    assert notifier.queue.get_nowait() is reminder


def test_queue_keeps_order_of_several_reminders():
    notifier = PopupQueueNotifier()

    notifier.send(make(1))
    notifier.send(make(2))

    assert [notifier.queue.get_nowait().id for _ in range(2)] == [1, 2]


def test_importing_popup_module_does_not_pull_tkinter():
    import sys

    assert "reminder.notifications.popup" in sys.modules
    assert "tkinter" not in sys.modules
