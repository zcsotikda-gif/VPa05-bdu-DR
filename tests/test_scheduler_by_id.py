"""Действия по id: планировщик перечитывает запись, а не верит снимку из окна.

Главное окно держит снимки записей. Если планировщик успел изменить статус
между обновлениями списка, действие по снимку сработало бы по устаревшим
данным — например, отложило бы уже завершённое напоминание.
"""

from datetime import UTC, datetime, timedelta

import pytest

from reminder.domain.models import Reminder, Status
from reminder.scheduler import Scheduler

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


class SilentNotifier:
    def send(self, reminder: Reminder) -> bool:
        return True


def build(storage) -> Scheduler:
    return Scheduler(storage=storage, notifier=SilentNotifier(), clock=lambda: NOW)


def test_snooze_by_id_moves_due_date(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(minutes=1))
    storage.update_status(reminder_id, Status.OVERDUE)

    build(storage).snooze_reminder(reminder_id)

    saved = storage.get(reminder_id)
    assert saved.due_at == NOW + timedelta(minutes=30)
    assert saved.status is Status.WAITING


def test_snooze_by_id_accepts_custom_delay(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW)

    build(storage).snooze_reminder(reminder_id, timedelta(hours=1))

    assert storage.get(reminder_id).due_at == NOW + timedelta(hours=1)


def test_snooze_by_id_refuses_reminder_that_became_final(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW - timedelta(minutes=1))
    storage.update_status(reminder_id, Status.DONE)
    before = storage.get(reminder_id).due_at

    with pytest.raises(ValueError, match="конечн"):
        build(storage).snooze_reminder(reminder_id)

    assert storage.get(reminder_id).due_at == before
    assert storage.get(reminder_id).status is Status.DONE


def test_snooze_by_id_reports_missing_reminder(storage):
    with pytest.raises(LookupError):
        build(storage).snooze_reminder(404)


def test_set_status_by_id_writes_status(storage):
    reminder_id = storage.add("Позвонить врачу", "", NOW)

    build(storage).set_status(reminder_id, Status.CANCELLED)

    assert storage.get(reminder_id).status is Status.CANCELLED
