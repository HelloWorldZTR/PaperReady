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
    is_complete: Callable[[PaperTask], bool]
    runner: Callable[[PaperTask, AppSettings], PaperTask]

    def describe(self) -> dict[str, str]:
        """Return a serializable step descriptor for API clients."""
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
        }


class PaperPipeline:
    """Run decoupled modules as a resumable local processing pipeline."""

    def __init__(self, steps: list[PipelineStep]) -> None:
        """Create a pipeline from ordered step definitions."""
        self.steps = steps

    def describe(self) -> list[dict[str, str]]:
        """Return the ordered pipeline shape for diagnostics and UI."""
        return [step.describe() for step in self.steps]

    def process(self, task: PaperTask, settings: AppSettings) -> PaperTask:
        """Advance one task through incomplete steps until blocked or ready."""
        if task.status in USER_BLOCKED_STATUSES:
            return task
        for step in self.steps:
            if step.is_complete(task):
                continue
            task = step.runner(task, settings)
            if task.status in USER_BLOCKED_STATUSES:
                break
        return task


def _run_locator(task: PaperTask, _: AppSettings) -> PaperTask:
    """Run the locator module with the pipeline runner signature."""
    return locate_paper(task)


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
                is_complete=lambda task: task.paper is not None,
                runner=_run_locator,
            ),
            PipelineStep(
                key="downloader",
                label="Paper Downloader",
                description="Attach user PDF, derive arXiv PDF, or mark metadata-only.",
                is_complete=lambda task: task.pdf is not None,
                runner=_run_downloader,
            ),
            PipelineStep(
                key="parser",
                label="PDF Parser",
                description="Create reusable semantic paper sections.",
                is_complete=lambda task: task.parsed is not None,
                runner=_run_parser,
            ),
            PipelineStep(
                key="evaluator",
                label="Paper Evaluator",
                description="Recommend reading value from metadata and sections.",
                is_complete=lambda task: task.evaluation is not None,
                runner=evaluate_task,
            ),
        ]
    )
