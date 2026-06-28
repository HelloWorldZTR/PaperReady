"""Tests for backend workflow services."""

from paper_ready_backend.models import AppSettings, ReportRequest, TaskRetryRequest
from paper_ready_backend.modules.parser import parse_text_sections
from paper_ready_backend.modules.zotero import build_zotero_payload, export_to_zotero
from paper_ready_backend.services import (
    create_tasks,
    describe_pipeline,
    detect_input_type,
    generate_report,
    process_task,
    retry_task,
)


def test_detect_input_type_handles_supported_inputs() -> None:
    """Input classification covers PRD v1 input types."""
    assert detect_input_type("10.1145/1234567") == "doi"
    assert detect_input_type("https://arxiv.org/abs/2401.12345") == "arxiv"
    assert detect_input_type("https://example.com/paper") == "url"
    assert detect_input_type("/tmp/example.pdf") == "local_pdf"
    assert detect_input_type("A Useful Paper Title") == "title"


def test_process_arxiv_task_reaches_report_ready() -> None:
    """A straightforward arXiv task advances through evaluation."""
    task = create_tasks(["2401.12345"])[0]
    processed = process_task(task, AppSettings(research_interests="paper demo"))
    assert processed.status == "Ready for report"
    assert processed.pdf_status == "PDF ready"
    assert processed.parser_status == "Parsed"
    assert processed.evaluation is not None


def test_pipeline_exposes_decoupled_modules() -> None:
    """The backend publishes the ordered pipeline subsystem."""
    keys = [step["key"] for step in describe_pipeline()]
    assert keys == ["locator", "downloader", "parser", "evaluator", "summarizer", "zotero"]
    assert describe_pipeline()[0]["mode"] == "automatic"
    assert describe_pipeline()[-1]["mode"] == "manual"


def test_retry_resets_from_selected_pipeline_step() -> None:
    """Retry clears downstream outputs before rerunning automatic modules."""
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    task = generate_report(task, AppSettings(), ReportRequest(report_type="Quick Brief"))
    retried = retry_task(task, TaskRetryRequest(step="evaluator"), AppSettings())
    assert retried.report is None
    assert retried.evaluation is not None
    assert retried.status == "Ready for report"


def test_budget_pause_prevents_report_generation() -> None:
    """Report generation pauses before exceeding configured budget."""
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    paused = generate_report(
        task,
        AppSettings(batch_budget=0.001),
        ReportRequest(report_type="Detailed Report"),
    )
    assert paused.status == "Budget paused"
    assert paused.report is None


def test_parser_extracts_coarse_semantic_sections() -> None:
    """Plain text parser recognizes common paper section headings."""
    sections = parse_text_sections(
        """
        Abstract
        This is the abstract.
        1 Introduction
        The intro text.
        Methods
        The method text.
        References
        [1] Example reference.
        """
    )
    assert sections["abstract"].startswith("This is")
    assert sections["introduction"].startswith("The intro")
    assert sections["method"].startswith("The method")


def test_zotero_bridge_builds_safe_payload_without_sqlite_write() -> None:
    """Zotero export prepares connector payloads and records local status."""
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    payload = build_zotero_payload(task, "Brief Reading")
    exported = export_to_zotero(task, "Brief Reading", AppSettings())
    assert payload["tags"] == ["Brief Reading"]
    assert payload["attachments"][0]["url"].startswith("https://arxiv.org/pdf/")
    assert exported.status == "Exported"
    assert exported.export_status == "Prepared: Brief Reading"
