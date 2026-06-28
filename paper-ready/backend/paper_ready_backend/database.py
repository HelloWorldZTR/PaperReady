"""SQLite persistence for the PaperReady local queue."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .models import AppSettings, PaperTask, utc_now


def get_db_path() -> Path:
    """Return the active SQLite path from the environment or backend folder."""
    override = os.getenv("PAPERREADY_DB_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "paper_ready.db"


def get_data_dir() -> Path:
    """Return the active local data directory for downloaded artifacts."""
    override = os.getenv("PAPERREADY_DATA_DIR")
    if override:
        return Path(override)
    return get_db_path().parent / "data"


def connect() -> sqlite3.Connection:
    """Open a SQLite connection with row dictionaries enabled."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables required by the durable task queue."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                raw_input TEXT NOT NULL,
                input_type TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _task_from_row(row: sqlite3.Row) -> PaperTask:
    """Decode a task row into a Pydantic model."""
    return PaperTask(**json.loads(row["payload"]))


def save_task(task: PaperTask) -> PaperTask:
    """Insert or replace a task and return the saved model."""
    task.updated_at = utc_now()
    payload = task.model_dump_json()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                task_id, raw_input, input_type, status, payload, created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                raw_input = excluded.raw_input,
                input_type = excluded.input_type,
                status = excluded.status,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                task.task_id,
                task.raw_input,
                task.input_type,
                task.status,
                payload,
                task.created_at,
                task.updated_at,
            ),
        )
    return task


def list_tasks() -> list[PaperTask]:
    """Return all tasks sorted by creation time."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM tasks ORDER BY created_at ASC"
        ).fetchall()
    return [_task_from_row(row) for row in rows]


def get_task(task_id: str) -> PaperTask | None:
    """Return one task by identifier, or None when it does not exist."""
    with connect() as conn:
        row = conn.execute(
            "SELECT payload FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    return _task_from_row(row) if row else None


def get_settings() -> AppSettings:
    """Return stored app settings, creating defaults on first use."""
    with connect() as conn:
        row = conn.execute("SELECT payload FROM settings WHERE id = 1").fetchone()
    if not row:
        settings = AppSettings()
        save_settings(settings)
        return settings
    return AppSettings(**json.loads(row["payload"]))


def save_settings(settings: AppSettings) -> AppSettings:
    """Persist app settings and return the saved model."""
    payload = settings.model_dump_json()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (id, payload, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (payload, utc_now()),
        )
    return settings


def export_payload() -> dict[str, Any]:
    """Return a compact database snapshot for diagnostics."""
    return {
        "db_path": str(get_db_path()),
        "task_count": len(list_tasks()),
        "settings": get_settings().model_dump(),
    }
