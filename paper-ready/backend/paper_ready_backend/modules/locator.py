"""Paper identity resolution module."""

from __future__ import annotations

from ..llm_client import complete_json
from ..models import AppSettings, PaperRecord, PaperTask
from ..prompts import LOCATOR_PROMPT
from .input_classifier import ARXIV_RE, DOI_RE


def locate_paper(task: PaperTask, settings: AppSettings | None = None) -> PaperTask:
    """Resolve one task into demo metadata or a disambiguation state."""
    task.status = "Locating"
    task.locator_status = "Locating"
    raw = task.raw_input.strip()
    arxiv_match = ARXIV_RE.search(raw)
    doi_match = DOI_RE.search(raw)

    llm_paper = _locate_with_llm(raw, settings) if settings else None
    if llm_paper:
        paper = llm_paper
    elif arxiv_match:
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


def _locate_with_llm(raw_input: str, settings: AppSettings | None) -> PaperRecord | None:
    """Resolve paper metadata with the configured LLM when credentials exist."""
    if not settings:
        return None
    payload = complete_json(
        settings,
        settings.locating_model,
        LOCATOR_PROMPT,
        f"Input: {raw_input}",
    )
    if not payload or not payload.get("title"):
        return None
    return PaperRecord(
        title=str(payload["title"]),
        authors=list(payload.get("authors") or []),
        year=payload.get("year"),
        venue=payload.get("venue"),
        doi=payload.get("doi"),
        arxiv_id=payload.get("arxiv_id"),
        urls=list(payload.get("urls") or []),
        abstract=payload.get("abstract"),
        source_confidence=float(payload.get("source_confidence") or 0.0),
        resolution_source="llm_locator",
        candidate_records=list(payload.get("candidate_records") or []),
    )
