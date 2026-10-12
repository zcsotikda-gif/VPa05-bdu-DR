"""Хранилище на SQLite: перевод между записью таблицы и `Reminder`.

Решений предметной области здесь нет — только чтение, запись и перевод
форматов. Что считать просроченным и когда звонить, решает
`reminder.domain.rules`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from reminder.clock import now_utc
from reminder.domain.models import Reminder, Status

_SCHEMA = Path(__file__).with_name("schema.sql")

_COLUMNS = "id, title, description, due_at, status, created_at, notified_at"


def _to_db(moment: datetime) -> str:
    """Время в строку: ISO-8601 в UTC с точностью до секунды — сортируется как строка."""
    if moment.tzinfo is None:
        raise ValueError("В базу пишется только время с часовым поясом")
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def _from_db(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(UTC)


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        due_at=_from_db(row["due_at"]),
        status=Status(row["status"]),
        notified_at=_from_db(row["notified_at"]),
    )


class SqliteStorage:
    """Напоминания в файле SQLite.

    Соединение открывается на каждую операцию: планировщик работает в своём
    потоке, и общее соединение потребовало бы разбираться с
    `check_same_thread`. При одном пользователе цена этого незаметна.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA.read_text(encoding="utf-8"))

    def add(self, title: str, description: str, due_at: datetime) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO reminders (title, description, due_at, status, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (title, description, _to_db(due_at), Status.WAITING.value, _to_db(now_utc())),
            )
            return cursor.lastrowid

    def get(self, reminder_id: int) -> Reminder | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
        return _row_to_reminder(row) if row is not None else None

    def list(self, status: Status | str | None = None) -> list[Reminder]:
        query = f"SELECT {_COLUMNS} FROM reminders"
        parameters: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            parameters = (str(status),)
        query += " ORDER BY due_at, id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_row_to_reminder(row) for row in rows]

    def update_status(self, reminder_id: int, status: Status | str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET status = ? WHERE id = ?", (str(status), reminder_id)
            )

    def mark_notified(self, reminder_id: int, at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET notified_at = ? WHERE id = ?", (_to_db(at), reminder_id)
            )

    def reschedule(self, reminder_id: int, due_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET due_at = ?, status = ?, notified_at = NULL WHERE id = ?",
                (_to_db(due_at), Status.WAITING.value, reminder_id),
            )

    def delete(self, reminder_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
