"""Legal PDF acquisition and metadata-only fallback module."""

from __future__ import annotations

from ..models import PaperTask, PdfRecord


def acquire_pdf(task: PaperTask) -> PaperTask:
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
        task.pdf = PdfRecord(
            paper_id=task.paper.paper_id,
            source_type="arxiv",
            source_url=f"https://arxiv.org/pdf/{task.paper.arxiv_id}",
            status="PDF ready",
            title_verified=True,
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

