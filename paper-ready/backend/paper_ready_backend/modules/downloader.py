"""Legal PDF acquisition and metadata-only fallback module."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

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
        direct_url = _direct_pdf_url(task)
        discovered_url = None if direct_url else _discover_pdf_url(task)
        source_url = direct_url or discovered_url
        if not source_url:
            task.pdf = PdfRecord(
                paper_id=task.paper.paper_id,
                source_type="metadata_only",
                status="PDF unavailable",
                failure_reason="No legal free PDF source found by downloader.",
            )
            task.status = "PDF unavailable"
            task.pdf_status = "PDF unavailable"
            task.next_action = "Evaluate metadata"
            return task
        local_path = _url_pdf_path(source_url, task.paper.paper_id)
        failure_reason = None
        if not local_path.exists():
            failure_reason = _download_pdf(source_url, local_path)
        task.pdf = PdfRecord(
            paper_id=task.paper.paper_id,
            source_type="free_url" if direct_url else "discovered_free_url",
            source_url=source_url,
            local_path=str(local_path) if local_path.exists() else None,
            status="PDF ready",
            failure_reason=failure_reason,
            title_verified=local_path.exists(),
        )

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


def _url_pdf_path(url: str, paper_id: str) -> Path:
    """Return the local cache path for a discovered free PDF URL."""
    name = Path(urlparse(url).path).name or f"{paper_id}.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{paper_id}.pdf"
    path = get_data_dir() / "pdfs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _direct_pdf_url(task: PaperTask) -> str | None:
    """Return a direct PDF URL from metadata when one is present."""
    for url in task.paper.urls if task.paper else []:
        if url.lower().split("?", 1)[0].endswith(".pdf"):
            return url
    return None


def _discover_pdf_url(task: PaperTask) -> str | None:
    """Find legal free PDF URLs advertised by a paper landing page."""
    for url in task.paper.urls if task.paper else []:
        discovered = discover_pdf_url(url)
        if discovered:
            return discovered
    return None


def discover_pdf_url(url: str) -> str | None:
    """Discover a PDF URL from common citation and link metadata."""
    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or response.content.startswith(b"%PDF"):
            return str(response.url)
        html = response.text
    except Exception:
        return None
    patterns = [
        r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+\.pdf[^"\']*)["\'][^>]+name=["\']citation_pdf_url["\']',
        r'<link[^>]+type=["\']application/pdf["\'][^>]+href=["\']([^"\']+)["\']',
        r'href=["\']([^"\']+\.pdf[^"\']*)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            return str(httpx.URL(url).join(match.group(1)))
    return None


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
