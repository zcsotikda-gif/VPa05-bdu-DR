"""Путь к файлу базы: по умолчанию рядом с проектом, переменная среды сильнее."""

from pathlib import Path

from reminder.config import DB_FILENAME, database_path


def test_environment_variable_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("REMINDER_DB", str(tmp_path / "custom.db"))

    assert database_path() == tmp_path / "custom.db"


def test_default_is_file_in_current_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("REMINDER_DB", raising=False)
    monkeypatch.chdir(tmp_path)

    assert database_path() == Path(tmp_path) / DB_FILENAME
