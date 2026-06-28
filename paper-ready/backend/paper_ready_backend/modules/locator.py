"""Paper identity resolution module."""

from __future__ import annotations

from ..llm_client import complete_json
from ..metadata import lookup_arxiv, lookup_doi, search_title
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

    deterministic = _locate_deterministic(raw, task)
    if task.status == "Needs disambiguation":
        return task
    llm_paper = _locate_with_llm(raw, settings) if settings and not deterministic else None
    if deterministic:
        paper = deterministic
    elif llm_paper and llm_paper.candidate_records and llm_paper.source_confidence < 0.75:
        return _needs_disambiguation(task, llm_paper.candidate_records)
    elif llm_paper:
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
        title_candidates = _fallback_title_candidates(raw)
        if title_candidates:
            return _needs_disambiguation(task, title_candidates)
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


def resolve_candidate(task: PaperTask, candidate_index: int) -> PaperTask:
    """Resolve a disambiguation task by selecting a candidate record."""
    candidates = (task.paper.candidate_records if task.paper else []) or []
    if candidate_index < 0 or candidate_index >= len(candidates):
        task.failure_reason = "Candidate index out of range"
        return task
    paper = PaperRecord(**candidates[candidate_index])
    return apply_resolved_paper(task, paper)


def apply_resolved_paper(task: PaperTask, paper: PaperRecord) -> PaperTask:
    """Apply user-selected or edited metadata and clear downstream outputs."""
    task.paper = paper
    task.paper_id = paper.paper_id
    task.status = "Located"
    task.locator_status = "Located"
    task.pdf = None
    task.pdf_status = "Queued"
    task.parsed = None
    task.parser_status = "Queued"
    task.evaluation = None
    task.evaluation_status = "Queued"
    task.report = None
    task.report_status = "Not requested"
    task.failure_reason = None
    task.next_action = "Attach or download PDF"
    return task


def _locate_deterministic(raw: str, task: PaperTask) -> PaperRecord | None:
    """Resolve metadata with deterministic academic APIs when possible."""
    arxiv_match = ARXIV_RE.search(raw)
    doi_match = DOI_RE.search(raw)
    if arxiv_match:
        return lookup_arxiv(arxiv_match.group(1))
    if doi_match:
        return lookup_doi(doi_match.group(1))
    if task.input_type == "title" and len(raw) >= 12:
        candidates = search_title(raw)
        if len(candidates) == 1 and candidates[0].source_confidence >= 0.72:
            return candidates[0]
        if len(candidates) > 1:
            task.status = "Needs disambiguation"
            task.locator_status = "Needs disambiguation"
            _needs_disambiguation(task, [candidate.model_dump() for candidate in candidates])
    return None


def _needs_disambiguation(
    task: PaperTask, candidates: list[dict] | list[PaperRecord]
) -> PaperTask:
    """Attach candidate records and pause for user disambiguation."""
    candidate_records = [
        candidate.model_dump() if isinstance(candidate, PaperRecord) else candidate
        for candidate in candidates
    ]
    task.paper = PaperRecord(
        title=task.raw_input,
        source_confidence=0.0,
        resolution_source="candidate_locator",
        candidate_records=candidate_records,
    )
    task.paper_id = task.paper.paper_id
    task.status = "Needs disambiguation"
    task.locator_status = "Needs disambiguation"
    task.next_action = "Choose a candidate"
    return task


def _fallback_title_candidates(raw: str) -> list[dict]:
    """Create local candidate records for visibly ambiguous title inputs."""
    if " or " not in raw.lower():
        return []
    parts = [part.strip() for part in raw.split(" or ") if part.strip()]
    return [
        PaperRecord(
            title=part,
            abstract="Local disambiguation candidate from ambiguous title input.",
            source_confidence=0.5,
            resolution_source="local_candidate",
        ).model_dump()
        for part in parts[:3]
    ]


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
