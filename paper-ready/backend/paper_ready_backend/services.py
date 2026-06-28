"""Compatibility service facade over decoupled modules and pipeline."""

from __future__ import annotations

from .models import (
    AppSettings,
    PaperTask,
    TaskResolveRequest,
    TaskRetryRequest,
    TaskYoloRequest,
)
from .modules.downloader import acquire_pdf
from .modules.evaluator import evaluate_task, override_recommendation
from .modules.input_classifier import create_tasks, detect_input_type
from .modules.locator import apply_resolved_paper, locate_paper, resolve_candidate
from .modules.parser import parse_pdf
from .modules.summarizer import estimate_report_cost, generate_report
from .modules.zotero import export_to_zotero, mark_exported
from .pipeline import default_pipeline


def describe_pipeline() -> list[dict[str, str | bool]]:
    """Return the ordered pipeline modules exposed by the backend."""
    return default_pipeline().describe()


def process_task(task: PaperTask, settings: AppSettings) -> PaperTask:
    """Advance one task through the default PaperReady pipeline."""
    return default_pipeline().process(task, settings)


def retry_task(task: PaperTask, request: TaskRetryRequest, settings: AppSettings) -> PaperTask:
    """Reset a task from a pipeline step and immediately process it."""
    reset = default_pipeline().reset_from(task, request.step)
    return process_task(reset, settings)


def resolve_task(task: PaperTask, request: TaskResolveRequest) -> PaperTask:
    """Resolve a user-blocked disambiguation task from candidate or metadata."""
    if request.paper:
        return apply_resolved_paper(task, request.paper)
    if request.candidate_index is not None:
        return resolve_candidate(task, request.candidate_index)
    task.failure_reason = "No candidate index or paper metadata provided"
    return task


def set_task_yolo(task: PaperTask, request: TaskYoloRequest) -> PaperTask:
    """Set or clear the task-level YOLO override."""
    task.yolo_enabled = request.enabled
    if task.status == "Ready for report":
        task.next_action = (
            "Run worker to generate report"
            if request.enabled
            else "Generate report"
        )
    return task
