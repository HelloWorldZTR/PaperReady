"""Safe Zotero export bridge module."""

from __future__ import annotations

from ..models import PaperTask


def mark_exported(task: PaperTask, category: str | None) -> PaperTask:
    """Record Zotero export intent without writing directly to Zotero storage."""
    task.status = "Exported"
    task.export_status = category or (
        task.evaluation.value_recommendation if task.evaluation else "Needs Review"
    )
    task.next_action = "Exported"
    return task

