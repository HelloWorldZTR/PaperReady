"""Background worker for resumable local queue processing."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

from . import database
from .models import AppSettings, PaperTask, ReportRequest
from .modules.summarizer import generate_report
from .pipeline import USER_BLOCKED_STATUSES, default_pipeline

AUTO_PAUSE_STATUSES = USER_BLOCKED_STATUSES | {
    "Ready for export",
}


class WorkerManager:
    """Own a background queue worker thread for the FastAPI process."""

    def __init__(self) -> None:
        """Create an idle worker manager."""
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.last_run_count = 0
        self.last_error: str | None = None

    def start(self) -> dict:
        """Start the background worker if it is not already running."""
        with self._lock:
            if self.is_running():
                return self.status()
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return self.status()

    def stop(self) -> dict:
        """Request worker shutdown and return current status."""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        return self.status()

    def is_running(self) -> bool:
        """Return whether the worker thread is alive."""
        return bool(self._thread and self._thread.is_alive())

    def status(self) -> dict:
        """Return serializable worker state for UI clients."""
        return {
            "running": self.is_running(),
            "last_run_count": self.last_run_count,
            "last_error": self.last_error,
        }

    def run_once(self) -> dict:
        """Process currently runnable tasks one pass through the pipeline."""
        settings = database.get_settings()
        tasks = [
            task for task in database.list_tasks() if _is_runnable(task, settings)
        ]
        if not tasks:
            self.last_run_count = 0
            return self.status()
        try:
            limiters = _stage_limiters(settings)
            max_workers = max(1, sum(limiters["limits"].values()))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(_process_and_save, task, settings, limiters["limiter"])
                    for task in tasks
                ]
                self.last_run_count = sum(1 for future in futures if future.result())
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
        return self.status()

    def _loop(self) -> None:
        """Worker loop that keeps polling the durable queue."""
        while not self._stop.is_set():
            self.run_once()
            time.sleep(1.0)


def _is_runnable(task: PaperTask, settings: AppSettings) -> bool:
    """Return whether automatic processing may advance this task."""
    if task.status == "Ready for report":
        return settings.yolo_default
    return task.status not in AUTO_PAUSE_STATUSES


def _process_and_save(task: PaperTask, settings: AppSettings, limiter) -> bool:
    """Process one task and persist the latest durable state."""
    processed = default_pipeline().process(task, settings, limiter)
    processed = _maybe_generate_yolo_report(processed, settings, limiter)
    database.save_task(processed)
    return True


def _maybe_generate_yolo_report(
    task: PaperTask, settings: AppSettings, limiter
) -> PaperTask:
    """Generate the report stage when unattended YOLO mode is enabled."""
    if not settings.yolo_default or task.status != "Ready for report":
        return task
    report_type = (
        task.evaluation.suggested_report_type
        if task.evaluation and task.evaluation.suggested_report_type
        else settings.default_report_type
    )
    with limiter("summarizer"):
        return generate_report(
            task,
            settings,
            ReportRequest(report_type=report_type),
        )


def _stage_limiters(settings: AppSettings) -> dict:
    """Create per-stage semaphores from user concurrency settings."""
    limits = {
        "locator": max(1, settings.locating_concurrency),
        "downloader": max(1, settings.locating_concurrency),
        "parser": max(1, settings.evaluation_concurrency),
        "evaluator": max(1, settings.evaluation_concurrency),
        "summarizer": max(1, settings.summarization_concurrency),
    }
    semaphores = {key: threading.Semaphore(value) for key, value in limits.items()}

    @contextmanager
    def limiter(stage_key: str) -> Iterator[None]:
        semaphore = semaphores.get(stage_key)
        if not semaphore:
            yield
            return
        with semaphore:
            yield

    return {"limits": limits, "limiter": limiter}


worker_manager = WorkerManager()
