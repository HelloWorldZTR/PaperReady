"""Report generation and budget enforcement module."""

from __future__ import annotations

from ..llm_client import complete_json, estimate_tokens
from ..models import AppSettings, PaperTask, ReportRecord, ReportRequest
from ..prompts import SUMMARY_PROMPT, prompt_template, render_prompt, report_prompt_key


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
    summary_input = _report_input(task, report_type, settings)
    input_tokens = estimate_tokens(summary_input)
    default_input, default_output, default_cost = estimate_report_cost(report_type)
    input_tokens = max(input_tokens, default_input)
    output_tokens = default_output
    cost = round((input_tokens + output_tokens) * 0.00001, 4)
    task.estimated_cost = cost
    if cost > settings.batch_budget:
        task.status = "Budget paused"
        task.report_status = "Budget paused"
        task.next_action = "Raise budget or choose a smaller report"
        return task

    task.status = "Summarizing"
    task.report_status = "Summarizing"
    sections = _generate_with_llm(settings, model_id, report_type, summary_input, task) or {
        "summary": f"{task.paper.title} is queued for deeper review.",
        "relevance": task.evaluation.rationale if task.evaluation else "",
    }
    task.report = ReportRecord(
        paper_id=task.paper.paper_id,
        report_type=report_type,
        sections=sections,
        model_id=model_id,
        input_token_estimate=input_tokens,
        output_token_estimate=output_tokens,
        estimated_cost=cost,
    )
    task.status = "Ready for export"
    task.report_status = "Generated"
    task.next_action = "Export to Zotero"
    return task


def _report_input(task: PaperTask, report_type: str, settings: AppSettings) -> str:
    """Build the report-generation input from metadata and parsed sections."""
    requested_sections = settings.report_types.get(report_type, [])
    paper = task.paper
    parsed = task.parsed
    return "\n".join(
        [
            f"Report type: {report_type}",
            f"Requested sections: {requested_sections}",
            f"Research interests: {settings.research_interests}",
            f"Research tags: {settings.research_tags}",
            f"Title: {paper.title if paper else ''}",
            f"Authors: {paper.authors if paper else []}",
            f"Year: {paper.year if paper else ''}",
            f"Venue: {paper.venue if paper else ''}",
            f"DOI: {paper.doi if paper else ''}",
            f"arXiv ID: {paper.arxiv_id if paper else ''}",
            f"Abstract: {paper.abstract if paper else ''}",
            f"Parse quality: {parsed.parse_quality if parsed else 'metadata_only'}",
            f"Sections: {parsed.sections if parsed else {}}",
            f"Figures: {parsed.figures if parsed else []}",
            f"Tables: {parsed.tables if parsed else []}",
            f"References: {parsed.references if parsed else []}",
            f"Evaluation: {task.evaluation.rationale if task.evaluation else ''}",
        ]
    )


def _generate_with_llm(
    settings: AppSettings,
    model_id: str,
    report_type: str,
    summary_input: str,
    task: PaperTask,
) -> dict[str, str] | None:
    """Generate report sections with the configured LLM when available."""
    prompt = render_prompt(
        prompt_template(settings, report_prompt_key(report_type), SUMMARY_PROMPT),
        _report_prompt_variables(task, settings),
    )
    payload = complete_json(settings, model_id, prompt, summary_input)
    sections = payload.get("sections") if payload else None
    if not isinstance(sections, dict):
        return None
    return {str(key): str(value) for key, value in sections.items()}


def _report_prompt_variables(task: PaperTask, settings: AppSettings) -> dict:
    """Return editable prompt variables for report generation."""
    paper = task.paper
    parsed = task.parsed
    sections = parsed.sections if parsed else {}
    return {
        "title": paper.title if paper else "",
        "abstract": paper.abstract if paper else "",
        "authors": paper.authors if paper else [],
        "venue": paper.venue if paper else "",
        "year": paper.year if paper else "",
        "doi": paper.doi if paper else "",
        "arxiv_id": paper.arxiv_id if paper else "",
        "pdf_text": "\n\n".join(sections.values()),
        "sections": sections,
        "references": parsed.references if parsed else [],
        "user_research_context": settings.research_interests,
        "value_recommendation": (
            task.evaluation.value_recommendation if task.evaluation else ""
        ),
    }
