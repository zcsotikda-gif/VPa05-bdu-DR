"""Системный баннер macOS через встроенный `osascript`.

Ставить ничего не нужно: `osascript` входит в macOS. Код возврата 0 означает
«отправлено», а не «человек увидел»: при включённом «Не беспокоить» или
отключённых уведомлениях для Script Editor баннер не покажется и об этом не
сообщит. Поэтому рядом работает второй уведомитель — окно.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from reminder.domain.models import Reminder

Runner = Callable[[list[str]], int]
"""Запуск процесса: получает argv, возвращает код возврата."""

DEFAULT_SOUND = "Purr"
"""Негромкий системный звук. Ping, Sosumi и Basso звучат как сигнал тревоги."""


def _run(argv: list[str]) -> int:
    return subprocess.run(argv, capture_output=True, check=False).returncode


def _escape(text: str) -> str:
    """Подготовить текст к вставке в строку AppleScript."""
    collapsed = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return collapsed.replace("\\", "\\\\").replace('"', '\\"')


class OsascriptBanner:
    """Уведомитель, показывающий баннер в Центре уведомлений macOS."""

    def __init__(self, runner: Runner = _run, sound: str = DEFAULT_SOUND) -> None:
        self._runner = runner
        self._sound = sound

    def send(self, reminder: Reminder) -> bool:
        body = reminder.description.strip() or reminder.title
        script = (
            f'display notification "{_escape(body)}"'
            f' with title "{_escape(reminder.title)}"'
            f' sound name "{_escape(self._sound)}"'
        )
        try:
            return self._runner(["osascript", "-e", script]) == 0
        except OSError:
            return False
