"""Хранилище SQLite: схема, запись, чтение, фильтр, перенос срока."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from reminder.domain.models import Status
from reminder.storage.sqlite import SqliteStorage

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


def test_init_schema_creates_table_on_empty_file(db_path):
    store = SqliteStorage(db_path)

    store.init_schema()

    assert store.list() == []


def test_init_schema_is_idempotent_and_keeps_data(storage):
    reminder_id = storage.add("Полить фикус", "", NOW)

    storage.init_schema()

    assert [r.id for r in storage.list()] == [reminder_id]


def test_added_reminder_is_read_back_field_by_field(storage):
    reminder_id = storage.add("Позвонить врачу", "записаться на приём", NOW)

    reminder = storage.get(reminder_id)

    assert reminder is not None
    assert reminder.id == reminder_id
    assert reminder.title == "Позвонить врачу"
    assert reminder.description == "записаться на приём"
    assert reminder.due_at == NOW
    assert reminder.status is Status.WAITING
    assert reminder.notified_at is None


def test_due_at_is_read_back_as_aware_utc(storage):
    reminder_id = storage.add("Встреча", "", NOW)

    due_at = storage.get(reminder_id).due_at

    assert due_at.tzinfo is not None
    assert due_at.utcoffset() == timedelta(0)
    assert due_at == NOW


def test_list_is_sorted_by_due_date(storage):
    later = storage.add("Поздно", "", NOW + timedelta(hours=2))
    sooner = storage.add("Рано", "", NOW)

    assert [r.id for r in storage.list()] == [sooner, later]


def test_list_filters_by_status(storage):
    waiting = storage.add("Ожидает", "", NOW)
    done = storage.add("Готово", "", NOW + timedelta(minutes=1))
    storage.update_status(done, Status.DONE)

    assert [r.id for r in storage.list(Status.WAITING)] == [waiting]
    assert [r.id for r in storage.list(Status.DONE)] == [done]


def test_update_status_changes_status(storage):
    reminder_id = storage.add("Задача", "", NOW)

    storage.update_status(reminder_id, Status.CANCELLED)

    assert storage.get(reminder_id).status is Status.CANCELLED


def test_mark_notified_stores_timestamp(storage):
    reminder_id = storage.add("Задача", "", NOW)

    storage.mark_notified(reminder_id, NOW)

    assert storage.get(reminder_id).notified_at == NOW


def test_reschedule_moves_due_date_back_to_waiting_and_clears_notification(storage):
    reminder_id = storage.add("Задача", "", NOW)
    storage.mark_notified(reminder_id, NOW)
    storage.update_status(reminder_id, Status.OVERDUE)

    storage.reschedule(reminder_id, NOW + timedelta(minutes=30))

    reminder = storage.get(reminder_id)
    assert reminder.due_at == NOW + timedelta(minutes=30)
    assert reminder.status is Status.WAITING
    assert reminder.notified_at is None


def test_delete_removes_reminder(storage):
    reminder_id = storage.add("Задача", "", NOW)

    storage.delete(reminder_id)

    assert storage.get(reminder_id) is None
    assert storage.list() == []


def test_unknown_status_is_rejected_by_database(storage):
    reminder_id = storage.add("Задача", "", NOW)

    with pytest.raises(sqlite3.IntegrityError):
        storage.update_status(reminder_id, "Почти готово")
