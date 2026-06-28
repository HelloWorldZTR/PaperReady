"""Safe Zotero export bridge module."""

from __future__ import annotations

import httpx

from ..models import AppSettings, PaperTask


def build_zotero_payload(
    task: PaperTask,
    category: str | None,
    include_pdf: bool = True,
    include_notes: bool = True,
) -> dict:
    """Build a safe connector-style payload for one processed paper."""
    paper = task.paper
    evaluation = task.evaluation
    report = task.report
    return {
        "task_id": task.task_id,
        "itemType": "journalArticle",
        "title": paper.title if paper else task.raw_input,
        "creators": [
            {"creatorType": "author", "name": author}
            for author in (paper.authors if paper else [])
        ],
        "date": str(paper.year) if paper and paper.year else None,
        "DOI": paper.doi if paper else None,
        "url": paper.urls[0] if paper and paper.urls else None,
        "abstractNote": paper.abstract if paper else None,
        "tags": [category or (evaluation.value_recommendation if evaluation else "Needs Review")],
        "collections": [category] if category else [],
        "attachments": _attachment_payload(task) if include_pdf else [],
        "notes": _notes_payload(report) if include_notes else [],
    }


def export_to_zotero(
    task: PaperTask,
    category: str | None,
    settings: AppSettings,
    include_pdf: bool = True,
    include_notes: bool = True,
) -> PaperTask:
    """Prepare or send a Zotero bridge payload without touching SQLite."""
    payload = build_zotero_payload(task, category, include_pdf, include_notes)
    task.export_status = f"Prepared: {payload['tags'][0]}"
    bridge_url = settings.zotero_bridge_url
    if bridge_url:
        try:
            response = httpx.post(bridge_url, json=payload, timeout=5.0)
            response.raise_for_status()
            task.export_status = f"Bridge sent: {payload['tags'][0]}"
        except Exception as exc:
            task.export_status = f"Bridge failed: {exc}"
    task.status = "Exported"
    task.next_action = "Exported"
    return task


def mark_exported(task: PaperTask, category: str | None) -> PaperTask:
    """Record Zotero export intent without writing directly to Zotero storage."""
    return export_to_zotero(task, category, AppSettings())


def _attachment_payload(task: PaperTask) -> list[dict[str, str]]:
    """Return optional PDF attachment descriptors for the connector bridge."""
    if not task.pdf or task.pdf.status != "PDF ready":
        return []
    payload = {"title": "PaperReady PDF", "mimeType": "application/pdf"}
    if task.pdf.local_path:
        payload["path"] = task.pdf.local_path
    if task.pdf.source_url:
        payload["url"] = task.pdf.source_url
    return [payload]


def _notes_payload(report) -> list[dict[str, str]]:
    """Return generated report sections as Zotero note payloads."""
    if not report:
        return []
    body = "\n\n".join(
        f"## {heading}\n{content}" for heading, content in report.sections.items()
    )
    return [{"title": f"PaperReady {report.report_type}", "body": body}]
