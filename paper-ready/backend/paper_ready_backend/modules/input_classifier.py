"""Input normalization and task creation helpers."""

from __future__ import annotations

import re

from ..models import PaperTask

ARXIV_RE = re.compile(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(v\d+)?", re.I)
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)


def detect_input_type(raw_input: str) -> str:
    """Classify one line of user input into a supported PRD input type."""
    value = raw_input.strip()
    lower = value.lower()
    if ARXIV_RE.search(value):
        return "arxiv"
    if DOI_RE.search(value):
        return "doi"
    if lower.startswith(("http://", "https://")):
        return "url"
    if lower.endswith(".pdf"):
        return "local_pdf"
    if value:
        return "title"
    return "unknown"


def create_tasks(inputs: list[str]) -> list[PaperTask]:
    """Build queued task models from non-empty batch input lines."""
    tasks = []
    for raw in inputs:
        value = raw.strip()
        if value:
            tasks.append(PaperTask(raw_input=value, input_type=detect_input_type(value)))
    return tasks
