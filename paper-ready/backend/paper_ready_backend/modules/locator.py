"""Paper identity resolution module."""

from __future__ import annotations

from ..models import PaperRecord, PaperTask
from .input_classifier import ARXIV_RE, DOI_RE


def locate_paper(task: PaperTask) -> PaperTask:
    """Resolve one task into demo metadata or a disambiguation state."""
    task.status = "Locating"
    task.locator_status = "Locating"
    raw = task.raw_input.strip()
    arxiv_match = ARXIV_RE.search(raw)
    doi_match = DOI_RE.search(raw)

    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
        paper = PaperRecord(
            title=f"arXiv paper {arxiv_id}",
            arxiv_id=arxiv_id,
            urls=[f"https://arxiv.org/abs/{arxiv_id}"],
            abstract="Demo metadata resolved from an arXiv identifier.",
            source_confidence=0.9,
        )
    elif doi_match:
        doi = doi_match.group(1)
        paper = PaperRecord(
            title=f"Paper with DOI {doi}",
            doi=doi,
            urls=[f"https://doi.org/{doi}"],
            abstract="Demo metadata resolved from a DOI-like input.",
            source_confidence=0.78,
        )
    elif task.input_type == "local_pdf":
        title = raw.rsplit("/", 1)[-1].removesuffix(".pdf")
        paper = PaperRecord(
            title=title.replace("_", " "),
            abstract="Metadata extracted from a user-provided PDF placeholder.",
            source_confidence=0.62,
        )
    elif task.input_type == "title" and len(raw) >= 12:
        paper = PaperRecord(
            title=raw,
            abstract="Title-only metadata requires later LLM or API enrichment.",
            source_confidence=0.55,
        )
    else:
        task.status = "Needs disambiguation"
        task.locator_status = "Needs disambiguation"
        task.next_action = "Choose a candidate or edit input"
        return task

    task.paper = paper
    task.paper_id = paper.paper_id
    task.status = "Located"
    task.locator_status = "Located"
    task.next_action = "Attach or download PDF"
    return task

