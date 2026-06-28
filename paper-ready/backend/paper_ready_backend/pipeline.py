"""Composable PaperReady pipeline subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import AppSettings, PaperTask
from .modules.downloader import acquire_pdf
from .modules.evaluator import evaluate_task
from .modules.locator import locate_paper
from .modules.parser import parse_pdf

USER_BLOCKED_STATUSES = {"Budget paused", "Exported", "Failed", "Needs disambiguation"}


@dataclass(frozen=True)
class PipelineStep:
    """Describe one idempotent pipeline step and its completion test."""

    key: str
    label: str
    description: str
    mode: str
    is_complete: Callable[[PaperTask], bool]
    runner: Callable[[PaperTask, AppSettings], PaperTask]

    def describe(self) -> dict[str, str | bool]:
        """Return a serializable step descriptor for API clients."""
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "mode": self.mode,
        }


class PaperPipeline:
    """Run decoupled modules as a resumable local processing pipeline."""

    def __init__(self, steps: list[PipelineStep]) -> None:
        """Create a pipeline from ordered step definitions."""
        self.steps = steps

    def describe(self) -> list[dict[str, str | bool]]:
        """Return the ordered pipeline shape for diagnostics and UI."""
        return [step.describe() for step in self.steps]

    def process(self, task: PaperTask, settings: AppSettings) -> PaperTask:
        """Advance one task through incomplete steps until blocked or ready."""
        if task.status in USER_BLOCKED_STATUSES:
            return task
        for step in self.steps:
            if step.mode != "automatic":
                continue
            if step.is_complete(task):
                continue
            task = step.runner(task, settings)
            if task.status in USER_BLOCKED_STATUSES:
                break
        return task

    def reset_from(self, task: PaperTask, step_key: str | None) -> PaperTask:
        """Clear durable step outputs so a task can retry from one module."""
        step = step_key or _infer_retry_step(task)
        if step == "locator":
            task.paper = None
            task.paper_id = None
            task.locator_status = "Queued"
        if step in {"locator", "downloader"}:
            task.pdf = None
            task.pdf_status = "Queued"
        if step in {"locator", "downloader", "parser"}:
            task.parsed = None
            task.parser_status = "Queued"
        if step in {"locator", "downloader", "parser", "evaluator"}:
            task.evaluation = None
            task.evaluation_status = "Queued"
        if step in {"locator", "downloader", "parser", "evaluator", "summarizer"}:
            task.report = None
            task.report_status = "Not requested"
        task.status = "Queued"
        task.failure_reason = None
        task.next_action = "Process task"
        return task


def _run_locator(task: PaperTask, _: AppSettings) -> PaperTask:
    """Run the locator module with the pipeline runner signature."""
    return locate_paper(task, _)


def _run_downloader(task: PaperTask, _: AppSettings) -> PaperTask:
    """Run the downloader module with the pipeline runner signature."""
    return acquire_pdf(task)


def _run_parser(task: PaperTask, _: AppSettings) -> PaperTask:
    """Run the parser module with the pipeline runner signature."""
    return parse_pdf(task)


def default_pipeline() -> PaperPipeline:
    """Build the default V1 pipeline from decoupled processing modules."""
    return PaperPipeline(
        [
            PipelineStep(
                key="locator",
                label="Paper Locator",
                description="Resolve raw input into paper metadata.",
                mode="automatic",
                is_complete=lambda task: task.paper is not None,
                runner=_run_locator,
            ),
            PipelineStep(
                key="downloader",
                label="Paper Downloader",
                description="Attach user PDF, derive arXiv PDF, or mark metadata-only.",
                mode="automatic",
                is_complete=lambda task: task.pdf is not None,
                runner=_run_downloader,
            ),
            PipelineStep(
                key="parser",
                label="PDF Parser",
                description="Create reusable semantic paper sections.",
                mode="automatic",
                is_complete=lambda task: task.parsed is not None,
                runner=_run_parser,
            ),
            PipelineStep(
                key="evaluator",
                label="Paper Evaluator",
                description="Recommend reading value from metadata and sections.",
                mode="automatic",
                is_complete=lambda task: task.evaluation is not None,
                runner=evaluate_task,
            ),
            PipelineStep(
                key="summarizer",
                label="Paper Summarizer",
                description="Generate selected configurable reports with budget checks.",
                mode="manual",
                is_complete=lambda task: task.report is not None,
                runner=lambda task, _: task,
            ),
            PipelineStep(
                key="zotero",
                label="Zotero Bridge",
                description="Export selected records without writing to Zotero SQLite.",
                mode="manual",
                is_complete=lambda task: task.status == "Exported",
                runner=lambda task, _: task,
            ),
        ]
    )


def _infer_retry_step(task: PaperTask) -> str:
    """Infer a retry starting point from the task's current failed state."""
    if task.status in {"Needs disambiguation", "Locating"}:
        return "locator"
    if task.status in {"PDF unavailable", "Downloading PDF"}:
        return "downloader"
    if task.status in {"Parse failed", "Parsing"}:
        return "parser"
    if task.status in {"Needs review", "Evaluating"}:
        return "evaluator"
    return "summarizer"
