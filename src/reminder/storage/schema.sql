-- Схема хранилища напоминаний. Применяется при каждом старте: IF NOT EXISTS
-- делает применение идемпотентным.

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    due_at      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Ожидает'
                CHECK (status IN ('Ожидает', 'Готово', 'Просрочено', 'Отменено')),
    created_at  TEXT NOT NULL,
    notified_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_reminders_status_due ON reminders (status, due_at);
