"""Порты: что правилам и планировщику нужно от внешнего мира.

Протоколы объявлены здесь, реализации живут в `storage/` и `notifications/`.
Ядро зависит от этих объявлений, а не от sqlite3, subprocess или tkinter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from reminder.domain.models import Reminder, Status


class Storage(Protocol):
    """Хранилище напоминаний.

    Ни один метод не принимает «сейчас»: временных правил в хранилище нет,
    их место — `reminder.domain.rules`.
    """

    def init_schema(self) -> None:
        """Создать таблицы, если их нет. Повторный вызов данные не трогает."""

    def add(self, title: str, description: str, due_at: datetime) -> int:
        """Добавить напоминание в статусе «Ожидает», вернуть его id."""

    def get(self, reminder_id: int) -> Reminder | None:
        """Вернуть напоминание или None, если такого нет."""

    def list(self, status: Status | str | None = None) -> list[Reminder]:
        """Вернуть напоминания, при указанном статусе — только с ним. Порядок по сроку."""

    def update_status(self, reminder_id: int, status: Status | str) -> None:
        """Записать статус. Недопустимое значение отвергается базой."""

    def mark_notified(self, reminder_id: int, at: datetime) -> None:
        """Отметить, что о напоминании звонили. Это отметка попытки, не факта просмотра."""

    def reschedule(self, reminder_id: int, due_at: datetime) -> None:
        """Перенести срок, вернуть в «Ожидает» и снять отметку о звонке."""

    def delete(self, reminder_id: int) -> None:
        """Удалить напоминание вместе с историей."""


class Notifier(Protocol):
    """Показ напоминания человеку.

    Возвращает False, если показать не удалось. True означает «отправлено»,
    а не «человек увидел»: системный баннер может быть подавлен настройками.
    """

    def send(self, reminder: Reminder) -> bool: ...
