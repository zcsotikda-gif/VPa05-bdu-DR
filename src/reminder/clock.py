"""Время приложения: человек вводит местное, хранится и сравнивается UTC.

Отдельный модуль нужен ещё и для подмены часов в тестах: планировщик
получает функцию «сколько сейчас», а не зовёт `datetime.now` сам.
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_utc() -> datetime:
    """Текущее время как aware-datetime в UTC."""
    return datetime.now(UTC)


def local_to_utc(entered: datetime) -> datetime:
    """Перевести введённое человеком местное время (без зоны) в UTC."""
    if entered.tzinfo is not None:
        raise ValueError("Ожидается местное время без часового пояса")
    return entered.astimezone(UTC)


def utc_to_local(moment: datetime) -> datetime:
    """Перевести время из UTC в местное — для показа человеку."""
    if moment.tzinfo is None:
        raise ValueError("Ожидается время с часовым поясом")
    return moment.astimezone()
