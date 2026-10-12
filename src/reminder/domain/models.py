"""Сущности предметной области и действия, которые возвращают правила.

Здесь нет ни SQL, ни подпроцессов, ни tkinter: модуль обязан импортироваться
в Linux-контейнере без Tk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    """Статусы из задания. Значения совпадают с тем, что лежит в БД."""

    WAITING = "Ожидает"
    DONE = "Готово"
    OVERDUE = "Просрочено"
    CANCELLED = "Отменено"


FINAL_STATUSES = frozenset({Status.DONE, Status.CANCELLED})
"""Конечные статусы: планировщик их не трогает и не уведомляет о них."""

MANUAL_STATUSES = (Status.DONE, Status.CANCELLED)
"""Статусы, которые человек ставит сам."""


@dataclass(frozen=True, slots=True)
class Reminder:
    """Напоминание. `due_at` и `notified_at` — всегда aware-время в UTC."""

    id: int
    title: str
    description: str
    due_at: datetime
    status: Status
    notified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Notify:
    """Показать напоминание человеку."""

    reminder: Reminder


@dataclass(frozen=True, slots=True)
class ChangeStatus:
    """Записать новый статус."""

    reminder_id: int
    status: Status


@dataclass(frozen=True, slots=True)
class Reschedule:
    """Перенести срок: хранилище возвращает запись в «Ожидает» и снимает отметку о звонке."""

    reminder_id: int
    due_at: datetime


Action = Notify | ChangeStatus | Reschedule
