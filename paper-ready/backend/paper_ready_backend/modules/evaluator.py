"""Reading-value evaluation module."""

from __future__ import annotations

from ..models import (
    AppSettings,
    EvaluationRecord,
    PaperTask,
    RecommendationOverride,
    ValueRecommendation,
)


def evaluate_task(task: PaperTask, settings: AppSettings) -> PaperTask:
    """Score reading value using metadata and configured research interests."""
    if not task.paper:
        return task
    interests = settings.research_interests.lower().split()
    section_text = list((task.parsed.sections if task.parsed else {}).values())
    haystack = " ".join([task.paper.title, task.paper.abstract or ""] + section_text).lower()
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

