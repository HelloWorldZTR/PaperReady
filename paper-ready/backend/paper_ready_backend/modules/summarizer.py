"""Report generation and budget enforcement module."""

from __future__ import annotations

from ..llm_client import complete_json, estimate_tokens
from ..models import AppSettings, PaperTask, ReportRecord, ReportRequest
from ..prompts import SUMMARY_PROMPT


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
    sections = _generate_with_llm(settings, model_id, summary_input) or {
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
    return "\n".join(
        [
            f"Report type: {report_type}",
            f"Research interests: {settings.research_interests}",
            f"Title: {task.paper.title if task.paper else ''}",
            f"Abstract: {task.paper.abstract if task.paper else ''}",
            f"Sections: {task.parsed.sections if task.parsed else {}}",
            f"Evaluation: {task.evaluation.rationale if task.evaluation else ''}",
        ]
    )


def _generate_with_llm(
    settings: AppSettings, model_id: str, summary_input: str
) -> dict[str, str] | None:
    """Generate report sections with the configured LLM when available."""
    payload = complete_json(settings, model_id, SUMMARY_PROMPT, summary_input)
    sections = payload.get("sections") if payload else None
    if not isinstance(sections, dict):
        return None
    return {str(key): str(value) for key, value in sections.items()}
