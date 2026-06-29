"""Paper identity resolution module."""

from __future__ import annotations

from ..llm_client import complete_json_with_web_search
from ..metadata import lookup_arxiv, lookup_doi
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

    local_candidates = _fallback_title_candidates(raw)
    if local_candidates:
        return _needs_disambiguation(task, local_candidates)

    exact = _locate_exact_identifier(raw)
    if exact:
        paper = exact
    else:
        llm_paper = _locate_with_llm_web_search(raw, settings)
        if llm_paper and llm_paper.arxiv_id:
            paper = _enrich_arxiv_paper(llm_paper)
        elif llm_paper and llm_paper.candidate_records and llm_paper.source_confidence < 0.75:
            return _needs_disambiguation(task, llm_paper.candidate_records)
        elif llm_paper:
            paper = llm_paper
        else:
            paper = None

    if paper:
        task.paper = paper
        task.paper_id = paper.paper_id
        task.status = "Located"
        task.locator_status = "Located"
        task.next_action = "Attach or download PDF"
        return task

    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
        paper = _fallback_arxiv_paper(arxiv_id)
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
    elif task.input_type == "url":
        paper = PaperRecord(
            title=_title_from_url(raw),
            urls=[raw],
            abstract="URL-only metadata requires later LLM or API enrichment.",
            source_confidence=0.52,
            resolution_source="url_fallback",
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


def _locate_exact_identifier(raw: str) -> PaperRecord | None:
    """Resolve exact arXiv or DOI identifiers without disambiguation."""
    arxiv_match = ARXIV_RE.search(raw)
    doi_match = DOI_RE.search(raw)
    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
        return lookup_arxiv(arxiv_id) or _fallback_arxiv_paper(arxiv_id)
    if doi_match:
        return lookup_doi(doi_match.group(1))
    return None


def _fallback_arxiv_paper(arxiv_id: str) -> PaperRecord:
    """Return a minimal successful match for a known arXiv identifier."""
    return PaperRecord(
        title=f"arXiv paper {arxiv_id}",
        arxiv_id=arxiv_id,
        urls=[f"https://arxiv.org/abs/{arxiv_id}"],
        abstract="Metadata lookup failed, but an arXiv identifier was found.",
        source_confidence=0.82,
        resolution_source="arxiv_url",
    )


def _enrich_arxiv_paper(paper: PaperRecord) -> PaperRecord:
    """Prefer arXiv API metadata after the LLM web search identifies arXiv."""
    if not paper.arxiv_id:
        return paper
    enriched = lookup_arxiv(paper.arxiv_id)
    if not enriched:
        paper.source_confidence = max(paper.source_confidence, 0.86)
        return paper
    enriched.source_confidence = max(enriched.source_confidence, paper.source_confidence)
    enriched.resolution_source = "llm_web_search_arxiv"
    return enriched


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


def _title_from_url(url: str) -> str:
    """Create a readable fallback title from a paper URL."""
    tail = url.rstrip("/").rsplit("/", 1)[-1] or url
    return tail.replace("-", " ").replace("_", " ").removesuffix(".pdf")


def _locate_with_llm_web_search(
    raw_input: str, settings: AppSettings | None
) -> PaperRecord | None:
    """Resolve paper metadata with model-managed web search when available."""
    if not settings:
        return None
    payload = complete_json_with_web_search(
        settings,
        settings.locating_model,
        LOCATOR_PROMPT,
        "\n".join(
            [
                f"Input: {raw_input}",
                "Use web search to find the exact paper.",
                "Prefer arXiv; if an arXiv page plausibly matches, return match_status='matched'.",
                "Return JSON only.",
            ]
        ),
    )
    if not payload or payload.get("match_status") == "not_found":
        return None
    if payload.get("match_status") == "ambiguous":
        candidates = list(payload.get("candidate_records") or [])
        return PaperRecord(
            title=raw_input,
            source_confidence=0.0,
            resolution_source="llm_web_search",
            candidate_records=candidates,
        )
    title = payload.get("title") or (
        f"arXiv paper {payload.get('arxiv_id')}" if payload.get("arxiv_id") else None
    )
    if not title:
        return None
    return PaperRecord(
        title=str(title),
        authors=list(payload.get("authors") or []),
        year=payload.get("year"),
        venue=payload.get("venue"),
        doi=payload.get("doi"),
        arxiv_id=payload.get("arxiv_id"),
        urls=list(payload.get("urls") or []),
        abstract=payload.get("abstract"),
        source_confidence=float(payload.get("source_confidence") or 0.0),
        resolution_source="llm_web_search",
        candidate_records=list(payload.get("candidate_records") or []),
    )
