"""Планировщик: читает ожидающие напоминания, спрашивает правила, исполняет ответ.

Решений здесь нет — только последовательность: взять, спросить, исполнить.
Что считать просроченным и когда звонить, решает `reminder.domain.rules`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from reminder.clock import now_utc
from reminder.domain.models import Action, ChangeStatus, Notify, Reschedule, Status
from reminder.domain.rules import DEFAULT_CATCH_UP, SNOOZE_DELAY, decide, snooze
from reminder.ports import Notifier, Storage

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 20.0
"""Как часто проверять сроки, в секундах."""


class Scheduler:
    """Фоновая проверка сроков.

    `on_change` вызывается после тика, который что-то изменил, — чтобы список
    в окне обновился. Он вызывается из фонового потока, поэтому должен быть
    потокобезопасным: ставить флаг или класть в очередь, а не трогать Tk.
    """

    def __init__(
        self,
        storage: Storage,
        notifier: Notifier,
        clock: Callable[[], datetime] = now_utc,
        interval: float = DEFAULT_INTERVAL,
        catch_up: timedelta = DEFAULT_CATCH_UP,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._storage = storage
        self._notifier = notifier
        self._clock = clock
        self._interval = interval
        self._catch_up = catch_up
        self._on_change = on_change
        self._stopping = threading.Event()

    def tick(self) -> None:
        """Один проход: взять ожидающие, решить, исполнить."""
        pending = self._storage.list(Status.WAITING)
        self.execute(decide(pending, self._clock(), self._catch_up))

    def execute(self, actions: Iterable[Action]) -> None:
        """Исполнить действия, пришедшие от правил."""
        changed = False
        for action in actions:
            match action:
                case Notify(reminder=reminder):
                    shown = self._notifier.send(reminder)
                    if not shown:
                        logger.warning("Напоминание %s показать не удалось", reminder.id)
                    # Отметка о попытке ставится независимо от успеха показа:
                    # иначе подавленный системой баннер звонил бы на каждом тике.
                    self._storage.mark_notified(reminder.id, self._clock())
                    changed = True
                case ChangeStatus(reminder_id=reminder_id, status=status):
                    self._storage.update_status(reminder_id, status)
                    changed = True
                case Reschedule(reminder_id=reminder_id, due_at=due_at):
                    self._storage.reschedule(reminder_id, due_at)
                    changed = True
        if changed and self._on_change is not None:
            self._on_change()

    def set_status(self, reminder_id: int, status: Status) -> None:
        """Поставить статус по id — так окно не зависит от своего снимка записи."""
        self.execute([ChangeStatus(reminder_id, status)])

    def snooze_reminder(self, reminder_id: int, delay: timedelta = SNOOZE_DELAY) -> None:
        """Отложить напоминание, перечитав его из хранилища.

        Окно держит снимки записей, а планировщик между обновлениями списка
        мог изменить статус. Перечитывание не даёт отложить то, что уже
        завершено: правило `snooze` увидит настоящий статус, а не устаревший.
        """
        reminder = self._storage.get(reminder_id)
        if reminder is None:
            raise LookupError(f"Напоминание {reminder_id} не найдено")
        self.execute(snooze(reminder, self._clock(), delay))

    def start(self) -> threading.Thread:
        """Запустить проверку в потоке-демоне: она живёт, пока живёт приложение."""
        self._stopping.clear()
        thread = threading.Thread(target=self._loop, name="reminder-scheduler", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        """Попросить поток остановиться после текущего тика."""
        self._stopping.set()

    def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("Сбой при проверке сроков")
            self._stopping.wait(self._interval)
