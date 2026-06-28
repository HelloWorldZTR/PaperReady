"""Report generation and budget enforcement module."""

from __future__ import annotations

from ..models import AppSettings, PaperTask, ReportRecord, ReportRequest


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

