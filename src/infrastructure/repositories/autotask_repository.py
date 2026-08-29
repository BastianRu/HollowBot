import json
import logging
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config import DATABASE_PATH

logger = logging.getLogger(__name__)

VALID_WEEKEND_MODES = {"STRICT_UNIVERSITY", "HARD_WORK_BALANCED", "FULL_REST"}
VALID_SETTINGS = {
    "timezone",
    "trench_days",
    "deep_work_days",
    "w_trench",
    "w_deep",
    "w_weekend_default",
    "max_trench_hours",
    "block_size",
    "weekend_mode",
}


def _parse_day_list(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple)):
        values = [int(item) for item in raw_value]
    elif isinstance(raw_value, str):
        cleaned = raw_value.strip()
        if not cleaned:
            return []
        if cleaned.startswith("["):
            values = json.loads(cleaned)
        else:
            values = [piece.strip() for piece in cleaned.split(",") if piece.strip()]
        values = [int(item) if not isinstance(item, int) else item for item in values]
    else:
        values = [int(raw_value)]

    normalized = []
    for value in values:
        if not 0 <= int(value) <= 6:
            raise ValueError("Los días deben estar entre 0 y 6")
        normalized.append(int(value))
    return sorted(set(normalized))


def _serialize_list(values):
    return json.dumps(list(values))


def _validate_setting(key, value):
    if key == "timezone":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("La zona horaria no puede estar vacía.")
        try:
            ZoneInfo(value.strip())
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Zona horaria inválida: {value}") from exc
        return value.strip()

    if key in {"trench_days", "deep_work_days"}:
        values = _parse_day_list(value)
        if not values:
            raise ValueError(f"{key} no puede estar vacío.")
        return values

    if key in {"w_trench", "w_deep", "w_weekend_default", "max_trench_hours", "block_size"}:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} debe ser numérico.") from exc
        if numeric <= 0:
            raise ValueError(f"{key} debe ser mayor que 0.")
        return numeric

    if key == "weekend_mode":
        mode = str(value).strip().upper()
        if mode not in VALID_WEEKEND_MODES:
            raise ValueError("weekend_mode inválido. Usa STRICT_UNIVERSITY, HARD_WORK_BALANCED o FULL_REST.")
        return mode

    raise ValueError(f"Parámetro no soportado: {key}")


def _default_user_settings():
    return {
        "timezone": "America/Bogota",
        "trench_days": [0, 2, 4],
        "deep_work_days": [1, 3],
        "w_trench": 0.2,
        "w_deep": 1.5,
        "w_weekend_default": 1.0,
        "max_trench_hours": 1.5,
        "block_size": 2.0,
        "weekend_mode": "HARD_WORK_BALANCED",
    }


def _row_to_settings(row):
    if not row:
        return _default_user_settings()

    columns = [
        "user_id",
        "timezone",
        "trench_days",
        "deep_work_days",
        "w_trench",
        "w_deep",
        "w_weekend_default",
        "max_trench_hours",
        "block_size",
        "weekend_mode",
    ]
    data = dict(zip(columns, row))
    return {
        "timezone": data.get("timezone", "America/Bogota"),
        "trench_days": json.loads(data.get("trench_days", "[0, 2, 4]")),
        "deep_work_days": json.loads(data.get("deep_work_days", "[1, 3]")),
        "w_trench": float(data.get("w_trench", 0.2)),
        "w_deep": float(data.get("w_deep", 1.5)),
        "w_weekend_default": float(data.get("w_weekend_default", 1.0)),
        "max_trench_hours": float(data.get("max_trench_hours", 1.5)),
        "block_size": float(data.get("block_size", 2.0)),
        "weekend_mode": data.get("weekend_mode", "HARD_WORK_BALANCED"),
    }


def get_user_settings(user_id):
    user_id = str(user_id)
    if not _ensure_autotask_schema():
        return _default_user_settings()
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            row = conn.execute(
                "SELECT * FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                default_data = _default_user_settings()
                conn.execute(
                    """
                    INSERT INTO user_settings (
                        user_id, timezone, trench_days, deep_work_days, w_trench,
                        w_deep, w_weekend_default, max_trench_hours, block_size, weekend_mode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        default_data["timezone"],
                        _serialize_list(default_data["trench_days"]),
                        _serialize_list(default_data["deep_work_days"]),
                        default_data["w_trench"],
                        default_data["w_deep"],
                        default_data["w_weekend_default"],
                        default_data["max_trench_hours"],
                        default_data["block_size"],
                        default_data["weekend_mode"],
                    ),
                )
                conn.commit()
                return default_data
            return _row_to_settings(row)
    except sqlite3.Error:
        logger.exception("Failed to load user settings for user_id=%s", user_id)
        return _default_user_settings()


def save_user_settings(user_id, **kwargs):
    user_id = str(user_id)
    if not _ensure_autotask_schema():
        return False

    payload = get_user_settings(user_id)
    for key, value in kwargs.items():
        if key not in VALID_SETTINGS:
            return False
        payload[key] = _validate_setting(key, value)

    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            conn.execute(
                """
                INSERT INTO user_settings (
                    user_id, timezone, trench_days, deep_work_days, w_trench,
                    w_deep, w_weekend_default, max_trench_hours, block_size, weekend_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    timezone = excluded.timezone,
                    trench_days = excluded.trench_days,
                    deep_work_days = excluded.deep_work_days,
                    w_trench = excluded.w_trench,
                    w_deep = excluded.w_deep,
                    w_weekend_default = excluded.w_weekend_default,
                    max_trench_hours = excluded.max_trench_hours,
                    block_size = excluded.block_size,
                    weekend_mode = excluded.weekend_mode
                """,
                (
                    user_id,
                    payload["timezone"],
                    _serialize_list(payload["trench_days"]),
                    _serialize_list(payload["deep_work_days"]),
                    payload["w_trench"],
                    payload["w_deep"],
                    payload["w_weekend_default"],
                    payload["max_trench_hours"],
                    payload["block_size"],
                    payload["weekend_mode"],
                ),
            )
            conn.commit()
        return True
    except sqlite3.Error:
        logger.exception("Failed to save user settings for user_id=%s", user_id)
        return False
    except ValueError:
        logger.exception("Invalid user setting payload for user_id=%s", user_id)
        return False


def update_user_setting(user_id, key, value):
    if key not in VALID_SETTINGS:
        return False
    try:
        cleaned_value = _validate_setting(key, value)
    except ValueError:
        return False
    return save_user_settings(user_id, **{key: cleaned_value})


def _ensure_autotask_schema():
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    timezone TEXT NOT NULL DEFAULT 'America/Bogota',
                    trench_days TEXT NOT NULL DEFAULT '[0, 2, 4]',
                    deep_work_days TEXT NOT NULL DEFAULT '[1, 3]',
                    w_trench REAL NOT NULL DEFAULT 0.2,
                    w_deep REAL NOT NULL DEFAULT 1.5,
                    w_weekend_default REAL NOT NULL DEFAULT 1.0,
                    max_trench_hours REAL NOT NULL DEFAULT 1.5,
                    block_size REAL NOT NULL DEFAULT 2.0,
                    weekend_mode TEXT NOT NULL DEFAULT 'HARD_WORK_BALANCED',
                    notification_channel_id INTEGER
                )
                """
            )
            conn.commit()
        return True
    except sqlite3.Error:
        logger.exception("Failed to ensure AutoTask schema for database %s", DATABASE_PATH)
        return False


def _reset_autotask_schema():
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            conn.execute("DROP TABLE IF EXISTS tasks")
            conn.execute("DROP TABLE IF EXISTS user_settings")
            conn.commit()
        return _ensure_autotask_schema()
    except sqlite3.Error:
        logger.exception("Failed to reset AutoTask schema for database %s", DATABASE_PATH)
        return False


def get_pending_tasks(user_id=None):
    if not _ensure_autotask_schema():
        return []

    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            if user_id is None:
                rows = conn.execute("SELECT * FROM tasks WHERE status = 'pending' ORDER BY id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = 'pending' AND user_id = ? ORDER BY id",
                    (str(user_id),),
                ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error:
        logger.exception("Failed to fetch pending tasks for user_id=%s", user_id)
        _reset_autotask_schema()
        return []
    except Exception:
        logger.exception("Unexpected error fetching pending tasks for user_id=%s", user_id)
        return []


def create_task(title, subject, due_date, estimated_hours, user_id=None, **kwargs):
    if not _ensure_autotask_schema():
        return None

    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (
                    title, subject, due_date, estimated_hours, created_at, status,
                    parent_id, is_subtask, block_number, total_blocks, user_id
                ) VALUES (?, ?, ?, ?, datetime('now'), 'pending', ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    subject,
                    due_date,
                    estimated_hours,
                    kwargs.get("parent_id"),
                    int(bool(kwargs.get("is_subtask", False))),
                    kwargs.get("block_number"),
                    kwargs.get("total_blocks"),
                    user_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create task for user_id=%s", user_id)
        _reset_autotask_schema()
        return None
    except Exception:
        logger.exception("Unexpected error creating task for user_id=%s", user_id)
        return None


def update_task_status(task_id, status):
    if not _ensure_autotask_schema():
        return False

    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to update task_status for task_id=%s", task_id)
        _reset_autotask_schema()
        return False
    except Exception:
        logger.exception("Unexpected error updating task_status for task_id=%s", task_id)
        return False
