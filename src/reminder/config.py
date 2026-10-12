"""Настройки приложения.

Путь к базе берётся из переменной среды `REMINDER_DB`, иначе — файл в текущем
каталоге. В `~/Library` ничего не создаётся намеренно: проект не должен
оставлять следов вне своего каталога.
"""

from __future__ import annotations

import os
from pathlib import Path

DB_FILENAME = "reminders.db"
DB_ENV_VAR = "REMINDER_DB"


def database_path() -> Path:
    """Путь к файлу базы."""
    configured = os.environ.get(DB_ENV_VAR)
    if configured is not None:
        return Path(configured)
    return Path.cwd() / DB_FILENAME
