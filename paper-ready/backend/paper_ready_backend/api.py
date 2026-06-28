"""FastAPI routes for the PaperReady local backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .models import (
    AppSettings,
    ExportRequest,
    ExportPreviewRequest,
    PaperTask,
    RecommendationOverride,
    ReportRequest,
    TaskCreateRequest,
    TaskResolveRequest,
    TaskRetryRequest,
    TaskYoloRequest,
)
from .services import (
    create_tasks,
    describe_pipeline,
    generate_report,
    export_to_zotero,
    override_recommendation,
    process_task,
    resolve_task,
    retry_task,
    set_task_yolo,
)
from .modules.zotero import build_zotero_payload, probe_zotero
from .worker import worker_manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local durable storage for the API process lifetime."""
    database.init_db()
    try:
        yield
    finally:
        worker_manager.stop()


app = FastAPI(title="PaperReady Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Return service health for Tauri and frontend readiness checks."""
    return {"status": "ok"}


@app.get("/debug/storage")
def storage_debug() -> dict:
    """Return a compact storage diagnostic snapshot."""
    return database.export_payload()


@app.get("/pipeline", response_model=list[dict])
def get_pipeline() -> list[dict[str, str | bool]]:
    """Return the ordered backend processing pipeline."""
    return describe_pipeline()


@app.get("/worker")
def get_worker_status() -> dict:
    """Return background worker status."""
    return worker_manager.status()


@app.post("/worker/start")
def post_worker_start() -> dict:
    """Start the background queue worker."""
    return worker_manager.start()


@app.post("/worker/stop")
def post_worker_stop() -> dict:
    """Stop the background queue worker."""
    return worker_manager.stop()


@app.post("/worker/run-once")
def post_worker_run_once() -> dict:
    """Run one worker pass over currently runnable tasks."""
    return worker_manager.run_once()


@app.get("/settings", response_model=AppSettings)
def get_settings() -> AppSettings:
    """Return persisted user settings."""
    return database.get_settings()


@app.put("/settings", response_model=AppSettings)
def put_settings(settings: AppSettings) -> AppSettings:
    """Replace persisted user settings."""
    return database.save_settings(settings)


@app.post("/tasks", response_model=list[PaperTask])
def post_tasks(request: TaskCreateRequest) -> list[PaperTask]:
    """Create queued tasks from batch inputs."""
    tasks = create_tasks(request.inputs)
    for task in tasks:
        database.save_task(task)
    return tasks


@app.get("/tasks", response_model=list[PaperTask])
def get_tasks() -> list[PaperTask]:
    """List all durable queue tasks."""
    return database.list_tasks()


def _load_task(task_id: str) -> PaperTask:
    """Load a task or raise the API-level 404 response."""
    task = database.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/process", response_model=PaperTask)
def post_process_task(task_id: str) -> PaperTask:
    """Advance one task through automatic workflow steps."""
    task = process_task(_load_task(task_id), database.get_settings())
    return database.save_task(task)


@app.post("/tasks/{task_id}/retry", response_model=PaperTask)
def post_retry_task(task_id: str, request: TaskRetryRequest) -> PaperTask:
    """Reset one task from a pipeline step and run automatic processing."""
    task = retry_task(_load_task(task_id), request, database.get_settings())
    return database.save_task(task)


@app.post("/tasks/{task_id}/resolve", response_model=PaperTask)
def post_resolve_task(task_id: str, request: TaskResolveRequest) -> PaperTask:
    """Resolve one task that is paused for user disambiguation."""
    task = resolve_task(_load_task(task_id), request)
    return database.save_task(task)


@app.post("/tasks/{task_id}/yolo", response_model=PaperTask)
def post_task_yolo(task_id: str, request: TaskYoloRequest) -> PaperTask:
    """Set or clear the task-level YOLO override."""
    task = set_task_yolo(_load_task(task_id), request)
    return database.save_task(task)


@app.post("/tasks/process-all", response_model=list[PaperTask])
def post_process_all() -> list[PaperTask]:
    """Advance every safe-to-run task once."""
    settings = database.get_settings()
    processed = []
    for task in database.list_tasks():
        processed.append(database.save_task(process_task(task, settings)))
    return processed


@app.post("/tasks/{task_id}/override", response_model=PaperTask)
def post_override(
    task_id: str, override: RecommendationOverride
) -> PaperTask:
    """Apply a manual value recommendation override."""
    task = override_recommendation(_load_task(task_id), override, database.get_settings())
    return database.save_task(task)


@app.post("/tasks/{task_id}/report", response_model=PaperTask)
def post_report(task_id: str, request: ReportRequest) -> PaperTask:
    """Generate a report for one selected task."""
    task = generate_report(_load_task(task_id), database.get_settings(), request)
    return database.save_task(task)


@app.post("/export/zotero", response_model=list[PaperTask])
def post_export(request: ExportRequest) -> list[PaperTask]:
    """Record a safe Zotero export operation for selected tasks."""
    exported = []
    settings = database.get_settings()
    for task_id in request.task_ids:
        task = export_to_zotero(
            _load_task(task_id),
            request.category,
            settings,
            include_pdf=request.include_pdf,
            include_notes=request.include_notes,
        )
        exported.append(database.save_task(task))
    return exported


@app.post("/export/zotero/preview")
def post_export_preview(request: ExportPreviewRequest) -> list[dict]:
    """Return connector-style Zotero payloads before the user confirms export."""
    payloads = []
    for task_id in request.task_ids:
        task = _load_task(task_id)
        payloads.append(
            build_zotero_payload(
                task,
                request.category,
                include_pdf=request.include_pdf,
                include_notes=request.include_notes,
            )
        )
    return payloads


@app.get("/zotero/status")
def get_zotero_status() -> dict:
    """Probe Zotero Connector readiness without writing to the library."""
    return probe_zotero(database.get_settings())
