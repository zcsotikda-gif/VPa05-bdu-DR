"""Правила напоминаний: что делать с ожидающими записями в момент `now`.

Чистые функции: ничего не читают, ничего не пишут, возвращают список действий.
Исполняет действия планировщик, а не правила.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from reminder.domain.models import (
    FINAL_STATUSES,
    Action,
    ChangeStatus,
    Notify,
    Reminder,
    Reschedule,
    Status,
)

DEFAULT_CATCH_UP = timedelta(minutes=5)
"""Насколько поздно ещё имеет смысл звонить о наступившем сроке.

Срок, пропущенный больше чем на это время (приложение было закрыто, ноутбук
спал), только помечается просроченным: звонок о вчерашнем шумит без пользы.
"""

SNOOZE_DELAY = timedelta(minutes=30)
"""Задержка быстрого действия «Отложить»."""


def decide(
    pending: Iterable[Reminder],
    now: datetime,
    catch_up: timedelta = DEFAULT_CATCH_UP,
) -> list[Action]:
    """Решить, что сделать с ожидающими напоминаниями в момент `now`.

    На вход подаются записи со статусом «Ожидает»; порядок входа сохраняется.
    """
    actions: list[Action] = []
    for reminder in pending:
        if reminder.status in FINAL_STATUSES or reminder.due_at > now:
            continue
        too_late = now - reminder.due_at > catch_up
        if reminder.notified_at is None and not too_late:
            actions.append(Notify(reminder))
        actions.append(ChangeStatus(reminder.id, Status.OVERDUE))
    return actions


def snooze(
    reminder: Reminder,
    now: datetime,
    delay: timedelta = SNOOZE_DELAY,
) -> Sequence[Action]:
    """Отложить напоминание: перенести срок на `delay` вперёд от `now`."""
    if reminder.status in FINAL_STATUSES:
        raise ValueError(f"Напоминание в конечном статусе «{reminder.status}» отложить нельзя")
    return [Reschedule(reminder.id, now + delay)]
