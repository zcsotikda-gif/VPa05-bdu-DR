"""Точка входа: единственное место, где части соединяются друг с другом.

Здесь выбираются реализации портов — SQLite как хранилище, баннер macOS и
окно как уведомители. Ни правила, ни планировщик, ни окно не знают, кого им
подсунули: они работают с протоколами из `reminder.ports`.
"""

from __future__ import annotations

import logging
import threading

from reminder.config import database_path
from reminder.notifications.banner import OsascriptBanner
from reminder.notifications.composite import CompositeNotifier
from reminder.notifications.popup import PopupQueueNotifier
from reminder.scheduler import Scheduler
from reminder.storage.sqlite import SqliteStorage


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    storage = SqliteStorage(database_path())
    storage.init_schema()

    popup = PopupQueueNotifier()
    notifier = CompositeNotifier([OsascriptBanner(), popup])

    refresh_signal = threading.Event()
    scheduler = Scheduler(storage=storage, notifier=notifier, on_change=refresh_signal.set)

    from reminder.ui.app import ReminderApp  # tkinter нужен только здесь

    app = ReminderApp(
        storage=storage, scheduler=scheduler, popup=popup, refresh_signal=refresh_signal
    )

    scheduler.start()
    try:
        app.run()
    finally:
        scheduler.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
