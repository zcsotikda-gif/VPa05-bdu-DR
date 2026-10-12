"""Окно напоминания поверх всех окон.

Зачем рядом с баннером: `osascript` сообщает «отправлено», а не «увидено» —
при «Не беспокоить» или отключённых уведомлениях баннер не покажется молча.
Окно от настроек системы не зависит.

Разделено на две части, потому что Tk можно трогать только из главного потока:
`PopupQueueNotifier` зовут из потока планировщика, а рисует `PopupPresenter`
в главном потоке. `tkinter` импортируется внутри методов — модуль обязан
импортироваться в контейнере без Tk.
"""

from __future__ import annotations

import queue
from collections.abc import Callable
from datetime import timedelta

from reminder.clock import utc_to_local
from reminder.domain.models import Reminder, Status
from reminder.domain.rules import SNOOZE_DELAY

POLL_MS = 500
"""Как часто главный поток заглядывает в очередь, в миллисекундах."""


class PopupQueueNotifier:
    """Уведомитель для фонового потока: кладёт напоминание в очередь."""

    def __init__(self) -> None:
        self.queue: queue.Queue[Reminder] = queue.Queue()

    def send(self, reminder: Reminder) -> bool:
        self.queue.put(reminder)
        return True


def _snooze_label(delay: timedelta = SNOOZE_DELAY) -> str:
    return f"Отложить на {int(delay.total_seconds() // 60)} мин"


class PopupPresenter:
    """Разбирает очередь и показывает окна. Живёт в главном потоке."""

    def __init__(
        self,
        root,
        notifier: PopupQueueNotifier,
        on_status: Callable[[Reminder, Status], None],
        on_snooze: Callable[[Reminder], None],
        poll_ms: int = POLL_MS,
    ) -> None:
        self._root = root
        self._notifier = notifier
        self._on_status = on_status
        self._on_snooze = on_snooze
        self._poll_ms = poll_ms

    def start(self) -> None:
        self._root.after(self._poll_ms, self._poll)

    def _poll(self) -> None:
        while True:
            try:
                reminder = self._notifier.queue.get_nowait()
            except queue.Empty:
                break
            self._show(reminder)
        self._root.after(self._poll_ms, self._poll)

    def _show(self, reminder: Reminder) -> None:
        import tkinter as tk
        from tkinter import ttk

        window = tk.Toplevel(self._root)
        window.title("Напоминание")
        window.attributes("-topmost", True)
        window.resizable(False, False)

        frame = ttk.Frame(window, padding=16)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text=reminder.title, font=("", 15, "bold"), wraplength=360).grid(
            row=0, column=0, sticky="w"
        )
        when = utc_to_local(reminder.due_at).strftime("%d.%m.%Y %H:%M")
        ttk.Label(frame, text=when, foreground="#777").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        if reminder.description.strip():
            ttk.Label(frame, text=reminder.description, wraplength=360).grid(
                row=2, column=0, sticky="w", pady=(8, 0)
            )

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, sticky="e", pady=(16, 0))

        def finish(action: Callable[[], None]) -> None:
            action()
            window.destroy()

        ttk.Button(
            buttons,
            text=_snooze_label(),
            command=lambda: finish(lambda: self._on_snooze(reminder)),
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Отменить",
            command=lambda: finish(lambda: self._on_status(reminder, Status.CANCELLED)),
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Готово",
            command=lambda: finish(lambda: self._on_status(reminder, Status.DONE)),
        ).grid(row=0, column=2)

        window.update_idletasks()
        window.lift()
        # Звука здесь нет намеренно: его даёт баннер. `window.bell()` вызывает
        # системный сигнал тревоги — для напоминания это слишком резко.
