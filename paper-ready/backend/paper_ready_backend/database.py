"""SQLite persistence for the PaperReady local queue."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .models import AppSettings, PaperTask, utc_now
from .prompts import DEFAULT_PROMPT_TEMPLATES


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


def delete_task(task_id: str) -> bool:
    """Delete one task by identifier and report whether a row was removed."""
    with connect() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
    return cursor.rowcount > 0


def get_settings() -> AppSettings:
    """Return stored app settings, creating defaults on first use."""
    with connect() as conn:
        row = conn.execute("SELECT payload FROM settings WHERE id = 1").fetchone()
    if not row:
        settings = AppSettings()
        save_settings(settings)
        return settings
    settings = AppSettings(**json.loads(row["payload"]))
    if _merge_default_prompts(settings):
        save_settings(settings)
    return settings


def save_settings(settings: AppSettings) -> AppSettings:
    """Persist app settings and return the saved model."""
    _merge_default_prompts(settings)
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


def _merge_default_prompts(settings: AppSettings) -> bool:
    """Fill missing prompt template keys without overwriting user edits."""
    changed = False
    prompts = dict(settings.prompt_templates or {})
    for key, value in DEFAULT_PROMPT_TEMPLATES.items():
        if (
            key not in prompts
            or not str(prompts[key]).strip()
            or _is_legacy_default_prompt(key, str(prompts[key]))
        ):
            prompts[key] = value
            changed = True
    if changed:
        settings.prompt_templates = prompts
    return changed


def _is_legacy_default_prompt(key: str, value: str) -> bool:
    """Return whether a stored prompt is an old built-in default."""
    if "{{" in value:
        return False
    if key == "Evaluator prompt":
        return (
            "PaperReady's research-paper triage evaluator" in value
            and "Recommendation policy:" in value
        )
    if key.endswith("Report prompt"):
        return (
            "PaperReady's academic report writer" in value
            and "Section requirements:" in value
        )
    if key == "Zotero note prompt":
        return value.startswith("Convert generated report sections")
    return False


def export_payload() -> dict[str, Any]:
    """Return a compact database snapshot for diagnostics."""
    data_dir = get_data_dir()
    cache_size = 0
    if data_dir.exists():
        cache_size = sum(
            path.stat().st_size for path in data_dir.rglob("*") if path.is_file()
        )
    return {
        "db_path": str(get_db_path()),
        "data_dir": str(data_dir),
        "cache_size_bytes": cache_size,
        "task_count": len(list_tasks()),
        "settings": get_settings().model_dump(),
    }


def clear_cache(mode: str) -> dict[str, int]:
    """Remove cached local files for the requested cleanup mode."""
    data_dir = get_data_dir().resolve()
    removed = 0
    bytes_removed = 0
    candidates: set[Path] = set()
    tasks = list_tasks()
    if mode == "all":
        candidates = {path for path in data_dir.rglob("*") if path.is_file()} if data_dir.exists() else set()
    else:
        matching = [
            task
            for task in tasks
            if (mode == "failed" and task.status in {"Failed", "Parse failed"})
            or (mode == "exported" and task.status == "Exported")
        ]
        for task in matching:
            if task.pdf and task.pdf.local_path:
                candidates.add(Path(task.pdf.local_path))
    for path in candidates:
        try:
            resolved = path.resolve()
            if resolved.is_file() and resolved.is_relative_to(data_dir):
                size = resolved.stat().st_size
                resolved.unlink()
                removed += 1
                bytes_removed += size
        except OSError:
            continue
    return {"removed": removed, "bytes_removed": bytes_removed}
