"""Несколько уведомителей как один.

Зовёт всех по очереди и не останавливается на сбое: баннер может быть подавлен
настройками системы, и тогда напоминание должно показать окно.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from reminder.domain.models import Reminder
from reminder.ports import Notifier

logger = logging.getLogger(__name__)


class CompositeNotifier:
    """Показывает напоминание всеми способами; True — удался хотя бы один."""

    def __init__(self, notifiers: Sequence[Notifier]) -> None:
        self._notifiers = list(notifiers)

    def send(self, reminder: Reminder) -> bool:
        shown = False
        for notifier in self._notifiers:
            try:
                shown = notifier.send(reminder) or shown
            except Exception:
                logger.exception("Уведомитель %s не смог показать напоминание", notifier)
        return shown
