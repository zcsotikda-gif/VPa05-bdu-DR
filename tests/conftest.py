"""Общие приспособления тестов: база во временном файле, фиксированные часы."""

from datetime import UTC, datetime

import pytest

from reminder.storage.sqlite import SqliteStorage

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def db_path(tmp_path):
    """Путь к файлу БД, который pytest удалит вместе с временным каталогом."""
    return tmp_path / "reminders.db"


@pytest.fixture
def storage(db_path):
    store = SqliteStorage(db_path)
    store.init_schema()
    return store
