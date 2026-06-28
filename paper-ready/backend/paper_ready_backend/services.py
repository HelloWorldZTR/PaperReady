"""Workflow services for locating, processing, and exporting papers."""

from __future__ import annotations

import re

from .models import (
    AppSettings,
    EvaluationRecord,
    PaperRecord,
    PaperTask,
    ParsedPaper,
    PdfRecord,
    RecommendationOverride,
    ReportRecord,
    ReportRequest,
    ValueRecommendation,
    new_id,
)

LOCATOR_PROMPT = "Resolve one paper input into metadata. Prefer arXiv."
EVALUATION_PROMPT = "Judge reading value using interests and parsed sections."
SUMMARY_PROMPT = "Generate the requested report sections for one paper."

ARXIV_RE = re.compile(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(v\d+)?", re.I)
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)


def detect_input_type(raw_input: str) -> str:
    """Classify a line of user input into a supported PRD input type."""
    value = raw_input.strip()
    lower = value.lower()
    if lower.endswith(".pdf"):
        return "local_pdf"
    if ARXIV_RE.search(value):
        return "arxiv"
    if DOI_RE.search(value):
        return "doi"
    if lower.startswith(("http://", "https://")):
        return "url"
    if value:
        return "title"
    return "unknown"


def create_tasks(inputs: list[str]) -> list[PaperTask]:
    """Build queued task models from non-empty batch input lines."""
    tasks = []
    for raw in inputs:
        value = raw.strip()
        if value:
            tasks.append(PaperTask(raw_input=value, input_type=detect_input_type(value)))
    return tasks


def locate_paper(task: PaperTask) -> PaperTask:
    """Resolve one task into demo metadata or a user-disambiguation state."""
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


def parse_pdf(task: PaperTask) -> PaperTask:
    """Create a semantic parsed-paper representation for downstream steps."""
    if not task.paper:
        return task
    task.status = "Parsing"
    task.parser_status = "Parsing"
    if not task.pdf or task.pdf.status != "PDF ready":
        task.parsed = ParsedPaper(paper_id=task.paper.paper_id)
        task.parser_status = "Metadata only"
        task.next_action = "Evaluate paper"
        return task

    title = task.paper.title
    task.parsed = ParsedPaper(
        paper_id=task.paper.paper_id,
        sections={
            "abstract": task.paper.abstract or "",
            "introduction": f"Placeholder introduction for {title}.",
            "method": "Demo parser has not extracted method details yet.",
            "experiments": "Demo parser has not extracted experiments yet.",
            "conclusion": "Demo parser has not extracted conclusion yet.",
        },
        parse_quality="demo_sections",
    )
    task.status = "Evaluating"
    task.parser_status = "Parsed"
    task.next_action = "Evaluate paper"
    return task


def evaluate_task(task: PaperTask, settings: AppSettings) -> PaperTask:
    """Score reading value using metadata and configured research interests."""
    if not task.paper:
        return task
    interests = settings.research_interests.lower().split()
    haystack = " ".join(
        [task.paper.title, task.paper.abstract or ""]
        + list((task.parsed.sections if task.parsed else {}).values())
    ).lower()
    matches = sum(1 for word in set(interests) if len(word) > 3 and word in haystack)
    if matches >= 2:
        recommendation: ValueRecommendation = "Very Important"
        confidence = 0.72
        report_type = "Standard Report"
    elif matches == 1 or task.paper.source_confidence >= 0.75:
        recommendation = "Brief Reading"
        confidence = 0.62
        report_type = "Quick Brief"
    else:
        recommendation = "Needs Review"
        confidence = 0.5
        report_type = None

    task.evaluation = EvaluationRecord(
        paper_id=task.paper.paper_id,
        value_recommendation=recommendation,
        confidence=confidence,
        rationale=f"Matched {matches} research-interest terms in demo evaluator.",
        suggested_next_action="Generate report" if report_type else "Review manually",
        suggested_report_type=report_type,
        model_id=settings.evaluation_model,
    )
    task.status = "Ready for report" if report_type else "Needs review"
    task.evaluation_status = recommendation
    task.next_action = task.evaluation.suggested_next_action
    return task


def estimate_report_cost(report_type: str) -> tuple[int, int, float]:
    """Estimate report tokens and cost before an expensive model call."""
    size = {"Quick Brief": 900, "Standard Report": 1800, "Detailed Report": 3200}
    input_tokens = size.get(report_type, 1200)
    output_tokens = int(input_tokens * 0.45)
    return input_tokens, output_tokens, round((input_tokens + output_tokens) * 0.00001, 4)


def generate_report(
    task: PaperTask, settings: AppSettings, request: ReportRequest
) -> PaperTask:
    """Generate a configurable demo report while enforcing batch budget."""
    if not task.paper:
        return task
    report_type = request.report_type or settings.default_report_type
    model_id = request.model_id or settings.summarization_model
    input_tokens, output_tokens, cost = estimate_report_cost(report_type)
    task.estimated_cost = cost
    if cost > settings.batch_budget:
        task.status = "Budget paused"
        task.report_status = "Budget paused"
        task.next_action = "Raise budget or choose a smaller report"
        return task

    task.status = "Summarizing"
    task.report_status = "Summarizing"
    task.report = ReportRecord(
        paper_id=task.paper.paper_id,
        report_type=report_type,
        sections={
            "summary": f"{task.paper.title} is queued for deeper review.",
            "relevance": task.evaluation.rationale if task.evaluation else "",
        },
        model_id=model_id,
        input_token_estimate=input_tokens,
        output_token_estimate=output_tokens,
        estimated_cost=cost,
    )
    task.status = "Ready for export"
    task.report_status = "Generated"
    task.next_action = "Export to Zotero"
    return task


def override_recommendation(
    task: PaperTask, override: RecommendationOverride, settings: AppSettings
) -> PaperTask:
    """Apply a user-owned reading value override to a task."""
    if not task.paper:
        return task
    task.evaluation = EvaluationRecord(
        paper_id=task.paper.paper_id,
        value_recommendation=override.value_recommendation,
        confidence=1.0,
        rationale=override.rationale,
        suggested_next_action="Generate report",
        suggested_report_type=settings.default_report_type,
        model_id="user",
    )
    task.evaluation_status = override.value_recommendation
    task.status = "Ready for report"
    task.next_action = "Generate report"
    return task


def mark_exported(task: PaperTask, category: str | None) -> PaperTask:
    """Record Zotero export intent without writing directly to Zotero storage."""
    task.status = "Exported"
    task.export_status = category or (
        task.evaluation.value_recommendation if task.evaluation else "Needs Review"
    )
    task.next_action = "Exported"
    return task


def process_task(task: PaperTask, settings: AppSettings) -> PaperTask:
    """Advance one task through safe automatic MVP workflow steps."""
    if task.status in {"Exported", "Budget paused", "Needs disambiguation"}:
        return task
    task = locate_paper(task) if not task.paper else task
    if task.status == "Needs disambiguation":
        return task
    task = acquire_pdf(task) if not task.pdf else task
    task = parse_pdf(task) if not task.parsed else task
    task = evaluate_task(task, settings) if not task.evaluation else task
    return task

