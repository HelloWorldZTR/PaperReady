"""Tests for the FastAPI queue routes."""

from fastapi.testclient import TestClient

from paper_ready_backend import api as api_module
from paper_ready_backend.api import app
from paper_ready_backend.modules import downloader
from paper_ready_backend.modules import locator


def test_task_api_round_trip(tmp_path, monkeypatch) -> None:
    """Tasks are created, persisted, processed, and listed through the API."""
    monkeypatch.setenv("PAPERREADY_DB_PATH", str(tmp_path / "paperready.db"))
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(downloader, "_download_pdf", lambda _url, path: path.write_bytes(b"%PDF-1.4") and None)
    monkeypatch.setattr(
        api_module,
        "probe_zotero",
        lambda _settings: {
            "available": False,
            "connector_url": "mock",
            "selected": None,
            "error": None,
        },
    )
    with TestClient(app) as client:
        created = client.post("/tasks", json={"inputs": ["2401.12345"]})
        assert created.status_code == 200
        task_id = created.json()[0]["task_id"]
        assert created.json()[0]["batch_id"].startswith("batch_")

        processed = client.post(f"/tasks/{task_id}/process")
        assert processed.status_code == 200
        assert processed.json()["status"] == "Ready for report"

        pipeline = client.get("/pipeline")
        assert pipeline.status_code == 200
        assert pipeline.json()[0]["key"] == "locator"
        assert pipeline.json()[-1]["key"] == "zotero"

        prompt_defaults = client.get("/settings/prompt-defaults")
        assert prompt_defaults.status_code == 200
        assert "Paper value" in prompt_defaults.json()["Evaluator prompt"]
        assert "{{title}}" in prompt_defaults.json()["Evaluator prompt"]
        assert "{{user_research_context}}" in prompt_defaults.json()["Quick Brief prompt"]

        retried = client.post(f"/tasks/{task_id}/retry", json={"step": "downloader"})
        assert retried.status_code == 200
        assert retried.json()["pdf_status"] == "PDF ready"

        replacement = tmp_path / "replacement.pdf"
        replacement.write_bytes(b"%PDF-1.4")
        attached = client.post(
            f"/tasks/{task_id}/pdf",
            json={"path": str(replacement)},
        )
        assert attached.status_code == 200
        assert attached.json()["pdf"]["source_type"] == "user_upload"

        skipped = client.post(f"/tasks/{task_id}/skip-pdf")
        assert skipped.status_code == 200
        assert skipped.json()["pdf_status"] == "PDF unavailable"
        assert skipped.json()["parser_status"] == "Metadata only"

        ambiguous = client.post("/tasks", json={"inputs": ["Paper One or Paper Two"]})
        ambiguous_id = ambiguous.json()[0]["task_id"]
        blocked = client.post(f"/tasks/{ambiguous_id}/process")
        assert blocked.json()["status"] == "Needs disambiguation"
        resolved = client.post(
            f"/tasks/{ambiguous_id}/resolve", json={"candidate_index": 0}
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "Located"

        worker = client.post("/worker/run-once")
        assert worker.status_code == 200
        assert worker.json()["running"] is False

        preview = client.post(
            "/export/zotero/preview",
            json={
                "task_ids": [task_id],
                "include_pdf": False,
                "include_notes": False,
                "category": "Brief Reading",
            },
        )
        assert preview.status_code == 200
        assert preview.json()[0]["attachments"] == []
        assert preview.json()[0]["notes"] == []

        zotero_status = client.get("/zotero/status")
        assert zotero_status.status_code == 200
        assert zotero_status.json()["available"] is False

        cache_file = tmp_path / "data" / "cached.bin"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"cache")
        cleared = client.post("/debug/cache/clear", json={"mode": "all"})
        assert cleared.status_code == 200
        assert cleared.json()["removed"] >= 1
        assert not cache_file.exists()

        listed = client.get("/tasks")
        assert listed.status_code == 200
        assert listed.json()[0]["task_id"] == task_id

        deleted = client.delete(f"/tasks/{task_id}")
        assert deleted.status_code == 200
        assert all(task["task_id"] != task_id for task in deleted.json())


def test_worker_yolo_generates_report(tmp_path, monkeypatch) -> None:
    """YOLO settings let the worker continue through report generation."""
    monkeypatch.setenv("PAPERREADY_DB_PATH", str(tmp_path / "paperready.db"))
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    with TestClient(app) as client:
        settings = client.get("/settings").json()
        settings["yolo_default"] = True
        settings["default_report_type"] = "Quick Brief"
        saved = client.put("/settings", json=settings)
        assert saved.status_code == 200

        created = client.post("/tasks", json={"inputs": ["2401.12345"]})
        task_id = created.json()[0]["task_id"]
        worker = client.post("/worker/run-once")
        assert worker.status_code == 200
        assert worker.json()["last_run_count"] == 1

        task = client.get("/tasks").json()[0]
        assert task["task_id"] == task_id
        assert task["status"] == "Ready for export"
        assert task["report_status"] == "Generated"
        assert task["report"]["report_type"] == "Quick Brief"


def test_task_yolo_override_controls_worker(tmp_path, monkeypatch) -> None:
    """Task-level YOLO can opt a row into unattended report generation."""
    monkeypatch.setenv("PAPERREADY_DB_PATH", str(tmp_path / "paperready.db"))
    monkeypatch.setenv("PAPERREADY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        downloader,
        "_download_pdf",
        lambda _url, path: path.write_bytes(b"%PDF-1.4") and None,
    )
    with TestClient(app) as client:
        created = client.post("/tasks", json={"inputs": ["2401.12345"]})
        task_id = created.json()[0]["task_id"]
        toggled = client.post(f"/tasks/{task_id}/yolo", json={"enabled": True})
        assert toggled.status_code == 200
        assert toggled.json()["yolo_enabled"] is True

        worker = client.post("/worker/run-once")
        assert worker.status_code == 200
        task = client.get("/tasks").json()[0]
        assert task["status"] == "Ready for export"
        assert task["report_status"] == "Generated"
