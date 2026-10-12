"""Главное окно: список напоминаний, фильтр по статусу, действия.

Это слой интерфейса, и `tkinter` здесь импортируется прямо — ядро
(`domain`, `storage`, `scheduler`, `ports`) его не знает и работает без Tk.

Окно не решает предметных вопросов: оно собирает действия из
`reminder.domain.rules` и отдаёт их планировщику на исполнение.
"""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from reminder.clock import local_to_utc, now_utc, utc_to_local
from reminder.domain.models import Reminder, Status
from reminder.domain.rules import SNOOZE_DELAY
from reminder.notifications.popup import PopupPresenter, PopupQueueNotifier
from reminder.ports import Storage
from reminder.scheduler import Scheduler

ALL_STATUSES = "Все"
DATE_FORMAT = "%d.%m.%Y"
TIME_FORMAT = "%H:%M"
DATE_HINT = "ДД.ММ.ГГГГ"
TIME_HINT = "ЧЧ:ММ"
REFRESH_POLL_MS = 500


def _snooze_label(delay: timedelta = SNOOZE_DELAY) -> str:
    return f"Отложить на {int(delay.total_seconds() // 60)} мин"


class ReminderApp:
    """Окно приложения.

    `refresh_signal` ставит планировщик из своего потока; окно опрашивает
    флаг в главном потоке — так список обновляется без обращения к Tk извне.
    """

    def __init__(
        self,
        storage: Storage,
        scheduler: Scheduler,
        popup: PopupQueueNotifier,
        refresh_signal: threading.Event,
    ) -> None:
        self._storage = storage
        self._scheduler = scheduler
        self._refresh_signal = refresh_signal
        self._rows: dict[str, Reminder] = {}

        self._root = tk.Tk()
        self._root.title("Напоминалка")
        self._root.minsize(760, 380)
        self._filter = tk.StringVar(value=ALL_STATUSES)

        self._build_layout()
        self._presenter = PopupPresenter(
            self._root,
            popup,
            on_status=self._apply_status,
            on_snooze=self._snooze,
        )

    # --- сборка интерфейса -------------------------------------------------

    def _build_layout(self) -> None:
        frame = ttk.Frame(self._root, padding=12)
        frame.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(top, text="Статус:").grid(row=0, column=0, padx=(0, 6))
        chooser = ttk.Combobox(
            top,
            textvariable=self._filter,
            values=[ALL_STATUSES, *[s.value for s in Status]],
            state="readonly",
            width=14,
        )
        chooser.grid(row=0, column=1)
        chooser.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Button(top, text="Добавить…", command=self._open_add_dialog).grid(
            row=0, column=2, padx=(12, 0)
        )

        columns = ("due_at", "title", "status", "description")
        self._table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for column, heading, width in (
            ("due_at", "Срок", 140),
            ("title", "Заголовок", 220),
            ("status", "Статус", 110),
            ("description", "Описание", 260),
        ):
            self._table.heading(column, text=heading)
            self._table.column(column, width=width, anchor="w")
        self._table.grid(row=1, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self._table.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self._table.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for index, (text, command) in enumerate(
            (
                ("Готово", lambda: self._selected_status(Status.DONE)),
                ("Отменить", lambda: self._selected_status(Status.CANCELLED)),
                (_snooze_label(), self._selected_snooze),
                ("Удалить", self._delete_selected),
                ("Обновить", self.refresh),
            )
        ):
            ttk.Button(actions, text=text, command=command).grid(row=0, column=index, padx=(0, 8))

    # --- данные ------------------------------------------------------------

    def refresh(self) -> None:
        """Перечитать список из хранилища с учётом выбранного фильтра."""
        chosen = self._filter.get()
        status = None if chosen == ALL_STATUSES else chosen
        self._table.delete(*self._table.get_children())
        self._rows.clear()
        for reminder in self._storage.list(status):
            row_id = self._table.insert(
                "",
                "end",
                values=(
                    utc_to_local(reminder.due_at).strftime(f"{DATE_FORMAT} {TIME_FORMAT}"),
                    reminder.title,
                    reminder.status.value,
                    reminder.description,
                ),
            )
            self._rows[row_id] = reminder

    def _selected(self) -> Reminder | None:
        selection = self._table.selection()
        if not selection:
            messagebox.showinfo("Напоминалка", "Сначала выберите напоминание в списке.")
            return None
        return self._rows[selection[0]]

    # --- действия ----------------------------------------------------------

    def _apply_status(self, reminder: Reminder, status: Status) -> None:
        self._scheduler.set_status(reminder.id, status)
        self.refresh()

    def _snooze(self, reminder: Reminder) -> None:
        # Действие идёт по id: планировщик перечитает запись, и отложить уже
        # завершённое напоминание не получится даже по устаревшему снимку.
        try:
            self._scheduler.snooze_reminder(reminder.id)
        except (ValueError, LookupError) as error:
            messagebox.showwarning("Отложить не получилось", str(error))
        self.refresh()

    def _selected_status(self, status: Status) -> None:
        reminder = self._selected()
        if reminder is not None:
            self._apply_status(reminder, status)

    def _selected_snooze(self) -> None:
        reminder = self._selected()
        if reminder is not None:
            self._snooze(reminder)

    def _delete_selected(self) -> None:
        reminder = self._selected()
        if reminder is None:
            return
        if messagebox.askyesno("Удалить напоминание", f"Удалить «{reminder.title}» без возврата?"):
            self._storage.delete(reminder.id)
            self.refresh()

    # --- добавление --------------------------------------------------------

    def _open_add_dialog(self) -> None:
        dialog = tk.Toplevel(self._root)
        dialog.title("Новое напоминание")
        dialog.transient(self._root)
        dialog.resizable(False, False)

        body = ttk.Frame(dialog, padding=14)
        body.grid(sticky="nsew")

        title = tk.StringVar()
        description = tk.StringVar()
        default = utc_to_local(now_utc()) + timedelta(minutes=5)
        date = tk.StringVar(value=default.strftime(DATE_FORMAT))
        time_of_day = tk.StringVar(value=default.strftime(TIME_FORMAT))

        fields = (
            ("Заголовок", title, 34),
            ("Описание", description, 34),
            (f"Дата ({DATE_HINT})", date, 14),
            (f"Время ({TIME_HINT})", time_of_day, 14),
        )
        for row, (label, variable, width) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(body, textvariable=variable, width=width).grid(
                row=row, column=1, sticky="w", padx=(10, 0), pady=4
            )

        def save() -> None:
            if not title.get().strip():
                messagebox.showwarning("Нужен заголовок", "Заголовок не может быть пустым.")
                return
            try:
                entered = datetime.strptime(
                    f"{date.get().strip()} {time_of_day.get().strip()}",
                    f"{DATE_FORMAT} {TIME_FORMAT}",
                )
            except ValueError:
                messagebox.showwarning(
                    "Не разобрал дату",
                    f"Ожидается дата как {DATE_HINT} и время как {TIME_HINT}.",
                )
                return
            self._storage.add(title.get().strip(), description.get().strip(), local_to_utc(entered))
            dialog.destroy()
            self.refresh()

        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Отмена", command=dialog.destroy).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(buttons, text="Добавить", command=save).grid(row=0, column=1)

        dialog.bind("<Return>", lambda _event: save())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

    # --- запуск ------------------------------------------------------------

    def _poll_refresh_signal(self) -> None:
        if self._refresh_signal.is_set():
            self._refresh_signal.clear()
            self.refresh()
        self._root.after(REFRESH_POLL_MS, self._poll_refresh_signal)

    def run(self) -> None:
        """Показать окно и работать до закрытия."""
        self.refresh()
        self._presenter.start()
        self._root.after(REFRESH_POLL_MS, self._poll_refresh_signal)
        self._root.mainloop()
