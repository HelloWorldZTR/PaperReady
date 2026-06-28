"""Safe Zotero export bridge module."""

from __future__ import annotations

import httpx

from ..models import AppSettings, PaperTask

CONNECTOR_TIMEOUT = 5.0


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
    mode = settings.zotero_export_mode
    if mode == "bridge" and settings.zotero_bridge_url:
        try:
            response = httpx.post(settings.zotero_bridge_url, json=payload, timeout=CONNECTOR_TIMEOUT)
            response.raise_for_status()
            task.export_status = f"Bridge sent: {payload['tags'][0]}"
        except Exception as exc:
            task.export_status = f"Bridge failed: {exc}"
    elif mode == "connector":
        task.export_status = import_with_connector(payload, settings)
    else:
        task.export_status = f"Prepared: {payload['tags'][0]}"
    if "failed" in task.export_status.lower():
        task.status = "Ready for export"
        task.next_action = "Fix Zotero connection and retry export"
    else:
        task.status = "Exported"
        task.next_action = "Exported"
    return task


def mark_exported(task: PaperTask, category: str | None) -> PaperTask:
    """Record Zotero export intent without writing directly to Zotero storage."""
    return export_to_zotero(task, category, AppSettings())


def probe_zotero(settings: AppSettings) -> dict:
    """Probe Zotero Desktop connector readiness without writing."""
    base_url = settings.zotero_connector_url.rstrip("/")
    result = {
        "available": False,
        "connector_url": base_url,
        "selected": None,
        "error": None,
    }
    try:
        ping = httpx.get(f"{base_url}/connector/ping", timeout=CONNECTOR_TIMEOUT)
        if ping.status_code >= 400:
            ping = httpx.post(f"{base_url}/connector/ping", timeout=CONNECTOR_TIMEOUT)
        ping.raise_for_status()
        result["available"] = True
        result["selected"] = _selected_collection(base_url)
    except Exception as exc:
        result["error"] = str(exc)
    return result


def import_with_connector(payload: dict, settings: AppSettings) -> str:
    """Import one item through Zotero Connector using a RIS payload."""
    base_url = settings.zotero_connector_url.rstrip("/")
    session = payload["task_id"]
    ris = _payload_to_ris(payload)
    try:
        response = httpx.post(
            f"{base_url}/connector/import?session={session}",
            content=ris,
            headers={"Content-Type": "application/x-research-info-systems"},
            timeout=CONNECTOR_TIMEOUT,
        )
        response.raise_for_status()
        return f"Connector imported: {payload['tags'][0]}"
    except Exception as exc:
        return f"Connector failed: {exc}"


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


def _selected_collection(base_url: str) -> dict | None:
    """Read Zotero Connector selected target when available."""
    try:
        response = httpx.post(
            f"{base_url}/connector/getSelectedCollection",
            timeout=CONNECTOR_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _payload_to_ris(payload: dict) -> str:
    """Convert connector payload metadata into an RIS import string."""
    lines = ["TY  - JOUR"]
    _add_ris(lines, "TI", payload.get("title"))
    for creator in payload.get("creators", []):
        _add_ris(lines, "AU", creator.get("name"))
    _add_ris(lines, "PY", payload.get("date"))
    _add_ris(lines, "DO", payload.get("DOI"))
    _add_ris(lines, "UR", payload.get("url"))
    _add_ris(lines, "AB", payload.get("abstractNote"))
    for tag in payload.get("tags", []):
        _add_ris(lines, "KW", tag)
    for attachment in payload.get("attachments", []):
        _add_ris(lines, "L1", attachment.get("path") or attachment.get("url"))
    for note in payload.get("notes", []):
        _add_ris(lines, "N1", note.get("body"))
    lines.append("ER  -")
    return "\n".join(lines) + "\n"


def _add_ris(lines: list[str], tag: str, value: str | None) -> None:
    """Append one escaped RIS field when value exists."""
    if value:
        lines.append(f"{tag}  - {str(value).replace(chr(10), ' ')}")
