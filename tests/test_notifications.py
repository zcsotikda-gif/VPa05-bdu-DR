"""Уведомители: сборка команды osascript и поведение при сбое.

`osascript` есть только на macOS, поэтому запуск процесса подменяется: эти
тесты обязаны проходить и в Linux-контейнере.
"""

from datetime import UTC, datetime

from reminder.domain.models import Reminder, Status
from reminder.notifications.banner import OsascriptBanner
from reminder.notifications.composite import CompositeNotifier

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)


def make(title: str = "Позвонить врачу", description: str = "записаться") -> Reminder:
    return Reminder(
        id=1,
        title=title,
        description=description,
        due_at=NOW,
        status=Status.WAITING,
        notified_at=None,
    )


class FakeRunner:
    """Подмена запуска процесса: запоминает аргументы, отдаёт заданный код возврата."""

    def __init__(self, returncode: int = 0, raises: Exception | None = None) -> None:
        self.returncode = returncode
        self.raises = raises
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(argv)
        if self.raises is not None:
            raise self.raises
        return self.returncode


class RecordingNotifier:
    def __init__(self, result: bool) -> None:
        self.result = result
        self.seen: list[Reminder] = []

    def send(self, reminder: Reminder) -> bool:
        self.seen.append(reminder)
        return self.result


def test_banner_calls_osascript_with_title_and_text():
    runner = FakeRunner()

    assert OsascriptBanner(runner=runner).send(make()) is True

    argv = runner.calls[0]
    assert argv[0] == "osascript"
    assert argv[1] == "-e"
    assert "Позвонить врачу" in argv[2]
    assert "записаться" in argv[2]
    assert "display notification" in argv[2]


def test_banner_escapes_quotes_and_backslashes():
    runner = FakeRunner()

    OsascriptBanner(runner=runner).send(make(title='Купить "винт"', description="C:\\path"))

    script = runner.calls[0][2]
    assert '\\"винт\\"' in script
    assert "C:\\\\path" in script


def test_banner_replaces_newlines_with_spaces():
    runner = FakeRunner()

    OsascriptBanner(runner=runner).send(make(description="первая\nвторая"))

    script = runner.calls[0][2]
    assert "\n" not in script
    assert "первая вторая" in script


def test_banner_uses_title_when_description_is_empty():
    runner = FakeRunner()

    OsascriptBanner(runner=runner).send(make(description=""))

    assert "Позвонить врачу" in runner.calls[0][2]


def test_banner_uses_a_calm_default_sound():
    """Звук по умолчанию — негромкий. Ping и Sosumi звучат как сигнал тревоги."""
    runner = FakeRunner()

    OsascriptBanner(runner=runner).send(make())

    assert 'sound name "Purr"' in runner.calls[0][2]


def test_banner_reports_failure_on_nonzero_exit():
    assert OsascriptBanner(runner=FakeRunner(returncode=1)).send(make()) is False


def test_banner_reports_failure_when_osascript_is_missing():
    runner = FakeRunner(raises=FileNotFoundError("osascript"))

    assert OsascriptBanner(runner=runner).send(make()) is False


def test_composite_calls_every_notifier_even_after_failure():
    failing = RecordingNotifier(False)
    working = RecordingNotifier(True)
    reminder = make()

    assert CompositeNotifier([failing, working]).send(reminder) is True
    assert failing.seen == [reminder]
    assert working.seen == [reminder]


def test_composite_reports_failure_when_nobody_managed_to_show():
    composite = CompositeNotifier([RecordingNotifier(False), RecordingNotifier(False)])

    assert composite.send(make()) is False


def test_composite_survives_notifier_that_raises():
    class Broken:
        def send(self, reminder: Reminder) -> bool:
            raise RuntimeError("сломался")

    working = RecordingNotifier(True)

    assert CompositeNotifier([Broken(), working]).send(make()) is True
    assert len(working.seen) == 1
