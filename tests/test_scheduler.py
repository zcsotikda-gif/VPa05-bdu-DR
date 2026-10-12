"""Планировщик: читает ожидающие, спрашивает правила, исполняет действия.

Хранилище настоящее (SQLite во временном файле), подменены только уведомитель
и часы.
"""

from datetime import UTC, datetime, timedelta

from reminder.domain.models import Reminder, Status
from reminder.domain.rules import snooze
from reminder.scheduler import Scheduler

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


class FakeNotifier:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.seen: list[Reminder] = []

    def send(self, reminder: Reminder) -> bool:
        self.seen.append(reminder)
        return self.result


def build(storage, notifier, now=NOW, **kwargs) -> Scheduler:
    return Scheduler(storage=storage, notifier=notifier, clock=lambda: now, **kwargs)


def test_due_reminder_is_shown_and_marked_overdue(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(seconds=30))
    notifier = FakeNotifier()

    build(storage, notifier).tick()

    assert [r.id for r in notifier.seen] == [reminder_id]
    saved = storage.get(reminder_id)
    assert saved.status is Status.OVERDUE
    assert saved.notified_at == NOW


def test_second_tick_does_not_show_the_same_reminder_again(storage):
    storage.add("Позвонить врачу", "", NOW - timedelta(seconds=30))
    notifier = FakeNotifier()
    scheduler = build(storage, notifier)

    scheduler.tick()
    scheduler.tick()

    assert len(notifier.seen) == 1


def test_notification_attempt_is_recorded_even_when_display_failed(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(seconds=30))

    build(storage, FakeNotifier(result=False)).tick()

    assert storage.get(reminder_id).notified_at == NOW


def test_future_reminder_is_left_alone(storage):
    reminder_id = storage.add("Позже", "", NOW + timedelta(minutes=10))
    notifier = FakeNotifier()

    build(storage, notifier).tick()

    assert notifier.seen == []
    assert storage.get(reminder_id).status is Status.WAITING


def test_finished_reminder_is_left_alone(storage):
    reminder_id = storage.add("Сделано", "", NOW - timedelta(hours=1))
    storage.update_status(reminder_id, Status.DONE)
    notifier = FakeNotifier()

    build(storage, notifier).tick()

    assert notifier.seen == []
    assert storage.get(reminder_id).status is Status.DONE


def test_long_missed_reminder_is_marked_without_being_shown(storage):
    reminder_id = storage.add("Вчерашнее", "", NOW - timedelta(hours=9))
    notifier = FakeNotifier()

    build(storage, notifier).tick()

    assert notifier.seen == []
    assert storage.get(reminder_id).status is Status.OVERDUE


def test_change_callback_fires_only_when_something_changed(storage):
    storage.add("Позже", "", NOW + timedelta(minutes=10))
    changes: list[int] = []
    scheduler = build(storage, FakeNotifier(), on_change=lambda: changes.append(1))

    scheduler.tick()
    assert changes == []

    storage.add("Сейчас", "", NOW - timedelta(seconds=10))
    scheduler.tick()
    assert changes == [1]


def test_snooze_action_moves_the_reminder_back_into_waiting(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(seconds=30))
    scheduler = build(storage, FakeNotifier())
    scheduler.tick()

    scheduler.execute(snooze(storage.get(reminder_id), NOW))

    saved = storage.get(reminder_id)
    assert saved.due_at == NOW + timedelta(minutes=30)
    assert saved.status is Status.WAITING
    assert saved.notified_at is None


def test_snoozed_reminder_is_shown_again_when_its_new_time_comes(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(seconds=30))
    notifier = FakeNotifier()
    build(storage, notifier).tick()
    later = NOW + timedelta(minutes=30)

    build(storage, notifier).execute(snooze(storage.get(reminder_id), NOW))
    build(storage, notifier, now=later).tick()

    assert len(notifier.seen) == 2


def test_background_thread_shows_due_reminder_and_stops_on_request(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(seconds=30))
    notifier = FakeNotifier()
    scheduler = Scheduler(storage=storage, notifier=notifier, clock=lambda: NOW, interval=0.01)

    thread = scheduler.start()
    try:
        deadline = datetime.now(UTC) + timedelta(seconds=5)
        while not notifier.seen and datetime.now(UTC) < deadline:
            pass
    finally:
        scheduler.stop()
        thread.join(timeout=5)

    assert [r.id for r in notifier.seen] == [reminder_id]
    assert thread.daemon is True
    assert not thread.is_alive()
