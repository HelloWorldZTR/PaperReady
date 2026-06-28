"""Pydantic data contracts for the PaperReady backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    """Return an ISO timestamp for durable queue records."""
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    """Return a stable-looking identifier with the requested prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


InputType = Literal["doi", "arxiv", "url", "title", "local_pdf", "unknown"]
TaskStatus = Literal[
    "Queued",
    "Locating",
    "Needs disambiguation",
    "Located",
    "Downloading PDF",
    "PDF unavailable",
    "PDF ready",
    "Parsing",
    "Parse failed",
    "Evaluating",
    "Needs review",
    "Ready for report",
    "Summarizing",
    "Budget paused",
    "Ready for export",
    "Exported",
    "Failed",
]
ValueRecommendation = Literal[
    "Very Important",
    "Brief Reading",
    "Unrelated",
    "Needs Review",
]


class PaperRecord(BaseModel):
    paper_id: str = Field(default_factory=lambda: new_id("paper"))
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    urls: list[str] = Field(default_factory=list)
    abstract: str | None = None
    source_confidence: float = 0.0
    resolution_source: str = "demo_locator"
    candidate_records: list[dict[str, Any]] = Field(default_factory=list)


class PdfRecord(BaseModel):
    pdf_id: str = Field(default_factory=lambda: new_id("pdf"))
    paper_id: str
    source_type: str
    source_url: str | None = None
    local_path: str | None = None
    status: str
    failure_reason: str | None = None
    title_verified: bool = False
    created_at: str = Field(default_factory=utc_now)


class ParsedPaper(BaseModel):
    paper_id: str
    sections: dict[str, str] = Field(default_factory=dict)
    figures: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    parse_quality: str = "metadata_only"
    created_at: str = Field(default_factory=utc_now)


class EvaluationRecord(BaseModel):
    paper_id: str
    value_recommendation: ValueRecommendation
    confidence: float
    rationale: str
    suggested_next_action: str
    suggested_report_type: str | None = None
    model_id: str
    prompt_version: str = "evaluation_v1"
    created_at: str = Field(default_factory=utc_now)


class ReportRecord(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("report"))
    paper_id: str
    report_type: str
    sections: dict[str, str]
    model_id: str
    prompt_version: str = "summary_v1"
    input_token_estimate: int
    output_token_estimate: int
    estimated_cost: float
    actual_usage: dict[str, Any] | None = None
    created_at: str = Field(default_factory=utc_now)


class PaperTask(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    raw_input: str
    input_type: InputType
    status: TaskStatus = "Queued"
    paper_id: str | None = None
    locator_status: str = "Queued"
    pdf_status: str = "Queued"
    parser_status: str = "Queued"
    evaluation_status: str = "Queued"
    report_status: str = "Not requested"
    next_action: str = "Process task"
    estimated_cost: float = 0.0
    paper: PaperRecord | None = None
    pdf: PdfRecord | None = None
    parsed: ParsedPaper | None = None
    evaluation: EvaluationRecord | None = None
    report: ReportRecord | None = None
    export_status: str = "Not exported"
    failure_reason: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class AppSettings(BaseModel):
    research_interests: str = ""
    batch_budget: float = 3.0
    daily_budget: float | None = None
    monthly_budget: float | None = None
    llm_api_base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None
    locating_model: str = "gpt-4.1-mini"
    evaluation_model: str = "gpt-4.1-mini"
    summarization_model: str = "gpt-4.1"
    locating_concurrency: int = 2
    evaluation_concurrency: int = 2
    summarization_concurrency: int = 1
    default_report_type: str = "Quick Brief"
    yolo_default: bool = False
    budget_overflow_behavior: str = "pause"
    language_preference: str = "en"
    zotero_bridge_url: str | None = None
    report_types: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "Quick Brief": ["summary", "main_contribution", "relevance"],
            "Standard Report": ["problem", "method", "evidence", "limitations"],
            "Detailed Report": [
                "section_summary",
                "method",
                "experiments",
                "limitations",
            ],
        }
    )
    prompt_templates: dict[str, str] = Field(default_factory=dict)


class TaskCreateRequest(BaseModel):
    inputs: list[str]


class RecommendationOverride(BaseModel):
    value_recommendation: ValueRecommendation
    rationale: str = "User override"


class ReportRequest(BaseModel):
    report_type: str | None = None
    model_id: str | None = None


class TaskRetryRequest(BaseModel):
    step: Literal["locator", "downloader", "parser", "evaluator", "summarizer"] | None = None


class TaskResolveRequest(BaseModel):
    candidate_index: int | None = None
    paper: PaperRecord | None = None


class ExportRequest(BaseModel):
    task_ids: list[str]
    include_pdf: bool = True
    include_notes: bool = True
    category: ValueRecommendation | None = None


class ExportPreviewRequest(ExportRequest):
    pass
