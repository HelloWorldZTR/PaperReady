"""Tests for the FastAPI queue routes."""

from fastapi.testclient import TestClient

from paper_ready_backend.api import app


def test_task_api_round_trip(tmp_path, monkeypatch) -> None:
    """Tasks are created, persisted, processed, and listed through the API."""
    monkeypatch.setenv("PAPERREADY_DB_PATH", str(tmp_path / "paperready.db"))
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

        listed = client.get("/tasks")
        assert listed.status_code == 200
        assert listed.json()[0]["task_id"] == task_id
