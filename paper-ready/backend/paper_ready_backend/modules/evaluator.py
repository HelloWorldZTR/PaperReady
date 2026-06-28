"""Reading-value evaluation module."""

from __future__ import annotations

from ..llm_client import complete_json
from ..models import (
    AppSettings,
    EvaluationRecord,
    PaperTask,
    RecommendationOverride,
    ValueRecommendation,
)
from ..prompts import EVALUATION_PROMPT

RECOMMENDATIONS: set[str] = {
    "Very Important",
    "Brief Reading",
    "Unrelated",
    "Needs Review",
}


def evaluate_task(task: PaperTask, settings: AppSettings) -> PaperTask:
    """Score reading value using metadata and configured research interests."""
    if not task.paper:
        return task
    llm_evaluation = _evaluate_with_llm(task, settings)
    if llm_evaluation:
        task.evaluation = llm_evaluation
        task.status = (
            "Ready for report"
            if llm_evaluation.suggested_report_type
            else "Needs review"
        )
        task.evaluation_status = llm_evaluation.value_recommendation
        task.next_action = llm_evaluation.suggested_next_action
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


def _evaluate_with_llm(
    task: PaperTask, settings: AppSettings
) -> EvaluationRecord | None:
    """Evaluate reading value with the configured LLM when available."""
    section_text = task.parsed.sections if task.parsed else {}
    payload = complete_json(
        settings,
        settings.evaluation_model,
        EVALUATION_PROMPT,
        "\n".join(
            [
                f"Research interests: {settings.research_interests}",
                f"Title: {task.paper.title if task.paper else ''}",
                f"Abstract: {task.paper.abstract if task.paper else ''}",
                f"Sections: {section_text}",
            ]
        ),
    )
    recommendation = str(payload.get("value_recommendation")) if payload else ""
    if recommendation not in RECOMMENDATIONS:
        return None
    return EvaluationRecord(
        paper_id=task.paper.paper_id,
        value_recommendation=recommendation,
        confidence=float(payload.get("confidence") or 0.5),
        rationale=str(payload.get("rationale") or "LLM evaluator produced no rationale."),
        suggested_next_action=str(payload.get("suggested_next_action") or "Review manually"),
        suggested_report_type=payload.get("suggested_report_type"),
        model_id=settings.evaluation_model,
    )


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
