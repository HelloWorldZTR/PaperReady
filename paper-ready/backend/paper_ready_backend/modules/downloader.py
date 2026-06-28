"""Legal PDF acquisition and metadata-only fallback module."""

from __future__ import annotations

from pathlib import Path

import httpx

from ..database import get_data_dir
from ..models import AppSettings, PaperTask, PdfRecord


def acquire_pdf(task: PaperTask, _: AppSettings | None = None) -> PaperTask:
    """Attach a local PDF, derive an arXiv PDF URL, or keep metadata-only."""
    if not task.paper:
        return task
    task.status = "Downloading PDF"
    task.pdf_status = "Downloading PDF"
    if task.input_type == "local_pdf":
        task.pdf = PdfRecord(
            paper_id=task.paper.paper_id,
            source_type="user_upload",
            local_path=task.raw_input,
            status="PDF ready",
            title_verified=True,
        )
    elif task.paper.arxiv_id:
        source_url = f"https://arxiv.org/pdf/{task.paper.arxiv_id}"
        local_path = _arxiv_pdf_path(task.paper.arxiv_id)
        failure_reason = None
        if not local_path.exists():
            failure_reason = _download_pdf(source_url, local_path)
        task.pdf = PdfRecord(
            paper_id=task.paper.paper_id,
            source_type="arxiv",
            source_url=source_url,
            local_path=str(local_path) if local_path.exists() else None,
            status="PDF ready",
            failure_reason=failure_reason,
            title_verified=local_path.exists(),
        )
    else:
        task.pdf = PdfRecord(
            paper_id=task.paper.paper_id,
            source_type="metadata_only",
            status="PDF unavailable",
            failure_reason="No legal free PDF source found by demo downloader.",
        )
        task.status = "PDF unavailable"
        task.pdf_status = "PDF unavailable"
        task.next_action = "Evaluate metadata"
        return task

    task.status = "PDF ready"
    task.pdf_status = "PDF ready"
    task.next_action = "Parse PDF"
    return task


def _arxiv_pdf_path(arxiv_id: str) -> Path:
    """Return the local cache path for an arXiv PDF."""
    safe_id = arxiv_id.replace("/", "_")
    path = get_data_dir() / "pdfs" / f"arxiv_{safe_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _download_pdf(url: str, local_path: Path) -> str | None:
    """Download a legal free PDF URL to disk, returning a failure reason."""
    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            return f"Unexpected content type: {content_type or 'unknown'}"
        local_path.write_bytes(response.content)
        return None
    except Exception as exc:
        return str(exc)
