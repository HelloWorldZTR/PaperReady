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
    monkeypatch.setattr(locator, "search_title", lambda _title: [])
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

        processed = client.post(f"/tasks/{task_id}/process")
        assert processed.status_code == 200
        assert processed.json()["status"] == "Ready for report"

        pipeline = client.get("/pipeline")
        assert pipeline.status_code == 200
        assert pipeline.json()[0]["key"] == "locator"
        assert pipeline.json()[-1]["key"] == "zotero"

        retried = client.post(f"/tasks/{task_id}/retry", json={"step": "downloader"})
        assert retried.status_code == 200
        assert retried.json()["pdf_status"] == "PDF ready"

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

        listed = client.get("/tasks")
        assert listed.status_code == 200
        assert listed.json()[0]["task_id"] == task_id
