"""Compatibility service facade over decoupled modules and pipeline."""

from __future__ import annotations

from .models import AppSettings, PaperTask
from .modules.downloader import acquire_pdf
from .modules.evaluator import evaluate_task, override_recommendation
from .modules.input_classifier import create_tasks, detect_input_type
from .modules.locator import locate_paper
from .modules.parser import parse_pdf
from .modules.summarizer import estimate_report_cost, generate_report
from .modules.zotero import mark_exported
from .pipeline import default_pipeline


def describe_pipeline() -> list[dict[str, str]]:
    """Return the ordered pipeline modules exposed by the backend."""
    return default_pipeline().describe()


def process_task(task: PaperTask, settings: AppSettings) -> PaperTask:
    """Advance one task through the default PaperReady pipeline."""
    return default_pipeline().process(task, settings)

