"""Tests for backend workflow services."""

from paper_ready_backend.models import (
    AppSettings,
    PdfAttachRequest,
    ReportRequest,
    TaskRetryRequest,
)
from paper_ready_backend.modules import downloader
from paper_ready_backend.modules import locator
from paper_ready_backend.modules.parser import parse_text_sections
from paper_ready_backend.modules import zotero
from paper_ready_backend.modules.zotero import build_zotero_payload, export_to_zotero
from paper_ready_backend.services import (
    attach_local_pdf,
    create_tasks,
    describe_pipeline,
    detect_input_type,
    generate_report,
    process_task,
    resolve_task,
    retry_task,
)
from paper_ready_backend.models import PaperRecord, TaskResolveRequest


def test_detect_input_type_handles_supported_inputs() -> None:
    """Input classification covers PRD v1 input types."""
    assert detect_input_type("10.1145/1234567") == "doi"
    assert detect_input_type("https://arxiv.org/abs/2401.12345") == "arxiv"
    assert detect_input_type("https://example.com/paper") == "url"
    assert detect_input_type("/tmp/example.pdf") == "local_pdf"
    assert detect_input_type("A Useful Paper Title") == "title"


def test_process_arxiv_task_reaches_report_ready(tmp_path, monkeypatch) -> None:
    """A straightforward arXiv task advances through evaluation."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(downloader, "_download_pdf", lambda _url, path: path.write_bytes(b"%PDF-1.4") and None)
    task = create_tasks(["2401.12345"])[0]
    processed = process_task(task, AppSettings(research_interests="paper demo"))
    assert processed.status == "Ready for report"
    assert processed.pdf_status == "PDF ready"
    assert processed.pdf.local_path
    assert processed.parser_status == "Parsed"
    assert processed.evaluation is not None


def test_locator_uses_deterministic_doi_metadata(monkeypatch) -> None:
    """DOI tasks use deterministic metadata before demo fallback."""
    monkeypatch.setattr(
        locator,
        "lookup_doi",
        lambda doi: PaperRecord(
            title="Resolved DOI Paper",
            doi=doi,
            source_confidence=0.93,
            resolution_source="crossref",
        ),
    )
    task = process_task(create_tasks(["10.1145/1234567"])[0], AppSettings())
    assert task.paper.title == "Resolved DOI Paper"
    assert task.paper.resolution_source == "crossref"


def test_disambiguation_candidate_can_be_resolved(monkeypatch) -> None:
    """Ambiguous locating results pause and can be resolved by candidate index."""
    monkeypatch.setattr(locator, "search_title", lambda _title: [])
    task = process_task(create_tasks(["Paper One or Paper Two"])[0], AppSettings())
    assert task.status == "Needs disambiguation"
    assert len(task.paper.candidate_records) == 2
    resolved = resolve_task(task, TaskResolveRequest(candidate_index=1))
    assert resolved.status == "Located"
    assert resolved.paper.title == "Paper Two"
    assert resolved.pdf is None


def test_edited_metadata_resolution_clears_downstream_outputs(tmp_path, monkeypatch) -> None:
    """User-edited paper metadata resets downstream processing state."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    task = generate_report(task, AppSettings(), ReportRequest(report_type="Quick Brief"))
    resolved = resolve_task(
        task,
        TaskResolveRequest(
            paper=PaperRecord(
                title="User Edited Paper",
                authors=["Ada Lovelace"],
                year=2026,
                source_confidence=1,
                resolution_source="user_edit",
            )
        ),
    )
    assert resolved.paper.title == "User Edited Paper"
    assert resolved.status == "Located"
    assert resolved.pdf is None
    assert resolved.parsed is None
    assert resolved.evaluation is None
    assert resolved.report is None


def test_url_pdf_input_downloads_free_pdf(tmp_path, monkeypatch) -> None:
    """Direct PDF URLs are treated as legal free PDF sources."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    task = process_task(create_tasks(["https://example.org/paper.pdf"])[0], AppSettings())
    assert task.pdf.source_type == "free_url"
    assert task.pdf.local_path.endswith("paper.pdf")
    assert task.pdf_status == "PDF ready"


def test_url_landing_page_discovers_pdf(tmp_path, monkeypatch) -> None:
    """Landing page URLs can discover advertised citation PDF URLs."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(downloader, "discover_pdf_url", lambda _url: "https://e.org/free.pdf")
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    task = process_task(create_tasks(["https://example.org/paper"])[0], AppSettings())
    assert task.pdf.source_type == "discovered_free_url"
    assert task.pdf.source_url == "https://e.org/free.pdf"


def test_pipeline_exposes_decoupled_modules() -> None:
    """The backend publishes the ordered pipeline subsystem."""
    keys = [step["key"] for step in describe_pipeline()]
    assert keys == ["locator", "downloader", "parser", "evaluator", "summarizer", "zotero"]
    assert describe_pipeline()[0]["mode"] == "automatic"
    assert describe_pipeline()[-1]["mode"] == "manual"


def test_retry_resets_from_selected_pipeline_step(tmp_path, monkeypatch) -> None:
    """Retry clears downstream outputs before rerunning automatic modules."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(downloader, "_download_pdf", lambda _url, path: path.write_bytes(b"%PDF-1.4") and None)
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    task = generate_report(task, AppSettings(), ReportRequest(report_type="Quick Brief"))
    retried = retry_task(task, TaskRetryRequest(step="evaluator"), AppSettings())
    assert retried.report is None
    assert retried.evaluation is not None
    assert retried.status == "Ready for report"


def test_attach_local_pdf_clears_downstream_outputs(tmp_path, monkeypatch) -> None:
    """Replacing a local PDF resets parser, evaluation, and report outputs."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    replacement = tmp_path / "replacement.pdf"
    replacement.write_bytes(b"%PDF-1.4")
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    task = generate_report(task, AppSettings(), ReportRequest(report_type="Quick Brief"))
    attached = attach_local_pdf(task, PdfAttachRequest(path=str(replacement)))
    assert attached.pdf.local_path == str(replacement)
    assert attached.pdf.source_type == "user_upload"
    assert attached.status == "PDF ready"
    assert attached.parsed is None
    assert attached.evaluation is None
    assert attached.report is None


def test_budget_pause_prevents_report_generation(tmp_path, monkeypatch) -> None:
    """Report generation pauses before exceeding configured budget."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(downloader, "_download_pdf", lambda _url, path: path.write_bytes(b"%PDF-1.4") and None)
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


def test_zotero_bridge_builds_safe_payload_without_sqlite_write(tmp_path, monkeypatch) -> None:
    """Zotero export prepares connector payloads and records local status."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(downloader, "_download_pdf", lambda _url, path: path.write_bytes(b"%PDF-1.4") and None)
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    payload = build_zotero_payload(task, "Brief Reading")
    exported = export_to_zotero(task, "Brief Reading", AppSettings())
    assert payload["tags"] == ["Brief Reading"]
    assert payload["attachments"][0]["url"].startswith("https://arxiv.org/pdf/")
    assert exported.status == "Exported"
    assert exported.export_status == "Prepared: Brief Reading"


def test_zotero_preview_can_hide_pdf_and_notes(tmp_path, monkeypatch) -> None:
    """Zotero payload preview respects attachment and note toggles."""
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    task = generate_report(task, AppSettings(), ReportRequest(report_type="Quick Brief"))
    payload = build_zotero_payload(
        task,
        "Brief Reading",
        include_pdf=False,
        include_notes=False,
    )
    assert payload["attachments"] == []
    assert payload["notes"] == []


def test_zotero_connector_probe_reports_selected_collection(monkeypatch) -> None:
    """Zotero connector probe reads ping and selected target without writes."""
    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"libraryID": 1, "collection": "abc"}

    monkeypatch.setattr(zotero.httpx, "get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(zotero.httpx, "post", lambda *_args, **_kwargs: Response())
    status = zotero.probe_zotero(AppSettings())
    assert status["available"] is True
    assert status["selected"]["collection"] == "abc"


def test_zotero_connector_import_success(tmp_path, monkeypatch) -> None:
    """Connector mode imports RIS and marks the task exported on success."""
    class Response:
        def raise_for_status(self) -> None:
            pass

    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    monkeypatch.setattr(zotero.httpx, "post", lambda *_args, **_kwargs: Response())
    task = process_task(create_tasks(["2401.12345"])[0], AppSettings())
    exported = export_to_zotero(
        task,
        "Brief Reading",
        AppSettings(zotero_export_mode="connector"),
    )
    assert exported.status == "Exported"
    assert exported.export_status == "Connector imported: Brief Reading"
