import sqlite3

import pytest

from src.integrations.autotask.parser import parse_task_message
from src.integrations.autotask.priority_engine import (
    break_down_task,
    get_days_remaining,
    get_target_day,
    score_single_task,
    score_tasks,
    should_break_down_task,
)
from src.infrastructure.repositories import autotask_repository
from src.infrastructure.repositories.autotask_repository import (
    get_user_settings,
    save_user_settings,
    update_user_setting,
)


def test_parse_task_message_supports_autotask_format():
    task = parse_task_message("OS | Ver documental | mañana | 2")

    assert task["subject"] == "OS"
    assert task["title"] == "Ver documental"
    assert task["estimated_hours"] == 2.0
    assert task["due_date"]


def test_priority_engine_breaks_long_tasks_into_blocks():
    assert should_break_down_task(8.0, {"block_size": 2.0}) is True
    blocks = break_down_task(8.0, {"block_size": 2.0})

    assert len(blocks) == 4
    assert sum(hours for _, hours in blocks) == 8.0


def test_parse_task_message_accepts_spanish_aliases_for_tomorrow():
    task = parse_task_message("OS | Ver documental | manana | 2")

    assert task["subject"] == "OS"
    assert task["title"] == "Ver documental"
    assert task["estimated_hours"] == 2.0
    assert task["due_date"]


def test_get_pending_tasks_filters_by_user(tmp_path, monkeypatch):
    db_path = tmp_path / "autotask_test.db"
    monkeypatch.setattr(autotask_repository, "DATABASE_PATH", str(db_path))

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            due_date TEXT NOT NULL,
            estimated_hours REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'pending',
            parent_id INTEGER,
            is_subtask BOOLEAN DEFAULT 0,
            block_number INTEGER,
            total_blocks INTEGER,
            user_id TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO tasks (title, subject, due_date, estimated_hours, status, user_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("Tarea A", "OS", "2026-09-01", 2.0, "pending", "user_1"),
            ("Tarea B", "DB", "2026-09-02", 1.5, "pending", "user_2"),
        ],
    )
    conn.commit()
    conn.close()

    tasks = autotask_repository.get_pending_tasks(user_id="user_1")

    assert len(tasks) == 1
    assert tasks[0]["title"] == "Tarea A"
    assert tasks[0]["user_id"] == "user_1"


def test_repository_handles_sqlite_errors_gracefully(monkeypatch):
    def raise_database_error(*args, **kwargs):
        raise sqlite3.DatabaseError("DB unavailable")

    monkeypatch.setattr(autotask_repository, "DATABASE_PATH", ":memory:")
    monkeypatch.setattr(sqlite3, "connect", raise_database_error)

    assert autotask_repository.get_pending_tasks("user_1") == []
    assert autotask_repository.create_task("Title", "OS", "2026-09-01", 2.0, user_id="user_1") is None
    assert autotask_repository.update_task_status(1, "completed") is False


def test_repository_creates_missing_tables_automatically(tmp_path, monkeypatch):
    db_path = tmp_path / "missing_schema.db"
    monkeypatch.setattr(autotask_repository, "DATABASE_PATH", str(db_path))

    tasks = autotask_repository.get_pending_tasks("user_1")

    assert tasks == []
    assert (db_path).exists()

    created = autotask_repository.create_task("Title", "OS", "2026-09-01", 2.0, user_id="user_1")
    assert created is not None

    pending = autotask_repository.get_pending_tasks("user_1")
    assert len(pending) == 1
    assert pending[0]["title"] == "Title"


def test_priority_engine_falls_back_when_timezone_is_missing():
    weekday, iso_date = get_target_day({"timezone": "America/Bogota"})

    assert isinstance(weekday, int)
    assert isinstance(iso_date, str)
    assert get_days_remaining("2026-09-01", timezone="America/Bogota") >= 0


def test_single_task_priority_matches_ranked_score():
    task = {
        "subject": "Lab. Software II",
        "title": "Hacer modelo C4 e informe",
        "due_date": "2026-09-02",
        "estimated_hours": 3.0,
        "status": "pending",
    }
    user_settings = {"timezone": "America/Bogota", "w_trench": 0.2, "w_deep": 1.5, "w_weekend_default": 1.0, "trench_days": [0, 2, 4], "deep_work_days": [1, 3], "block_size": 2.0, "weekend_mode": "HARD_WORK_BALANCED"}

    direct_score = score_single_task(task, user_settings=user_settings)
    ranked_score = score_tasks([task], user_settings=user_settings)[0][1]

    assert abs(direct_score - ranked_score) < 1e-9


def test_user_settings_are_persisted_per_user(tmp_path, monkeypatch):
    db_path = tmp_path / "settings_test.db"
    monkeypatch.setattr(autotask_repository, "DATABASE_PATH", str(db_path))

    saved = save_user_settings(
        "user_42",
        timezone="UTC",
        trench_days=[0, 2],
        deep_work_days=[1, 3],
        w_trench=0.1,
        w_deep=1.2,
        max_trench_hours=1.5,
        block_size=2.0,
        weekend_mode="STRICT_UNIVERSITY",
    )

    assert saved is True

    stored = get_user_settings("user_42")
    assert stored["timezone"] == "UTC"
    assert stored["weekend_mode"] == "STRICT_UNIVERSITY"
    assert stored["trench_days"] == [0, 2]


def test_update_user_setting_validates_allowed_values(tmp_path, monkeypatch):
    db_path = tmp_path / "settings_validation.db"
    monkeypatch.setattr(autotask_repository, "DATABASE_PATH", str(db_path))

    assert update_user_setting("user_7", "weekend_mode", "FULL_REST") is True
    assert update_user_setting("user_7", "weekend_mode", "INVALID_MODE") is False
    assert update_user_setting("user_7", "block_size", 0) is False
    assert update_user_setting("user_7", "trench_days", "-1,99") is False
