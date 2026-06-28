# PaperReady

PaperReady is a local-first Tauri desktop app for batch processing research
papers. The current implementation is an MVP skeleton with a Vue task-list UI
and a FastAPI backend backed by SQLite.

## Architecture

- `src/`: Vue desktop UI with Home, Tasks, and Settings subpages.
- `backend/paper_ready_backend/llm_client.py`: OpenAI-compatible LLM boundary.
- `backend/paper_ready_backend/metadata.py`: arXiv and Crossref metadata helpers.
- `backend/paper_ready_backend/modules/`: decoupled paper workflow modules.
- `backend/paper_ready_backend/pipeline.py`: ordered pipeline subsystem.
- `backend/paper_ready_backend/worker.py`: local background queue worker.
- `src-tauri/`: Tauri shell that owns the desktop window lifecycle.

## Prerequisites

- Python 3.11+
- Node.js with `pnpm`
- Rust toolchain for Tauri

Install Python dependencies from the repository root:

```bash
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd paper-ready
pnpm install
```

## Run The Backend

The Tauri app attempts to start the backend automatically. For web-only
development, start it manually:

```bash
cd paper-ready/backend
python -m uvicorn paper_ready_backend.main:app --host 127.0.0.1 --port 8765
```

Useful environment variables:

- `PAPERREADY_DB_PATH`: override the SQLite database location.
- `PAPERREADY_DATA_DIR`: override the local artifact directory for cached PDFs.
- `PAPERREADY_PYTHON`: Python executable used by Tauri to start FastAPI.
- `PAPERREADY_BACKEND_EXTERNAL=1`: prevent Tauri from spawning the backend.

## Run The UI

Web-only development:

```bash
cd paper-ready
pnpm dev
```

Desktop development:

```bash
cd paper-ready
pnpm tauri dev
```

## Build

Build the Vue frontend:

```bash
cd paper-ready
pnpm build
```

Build the Tauri app:

```bash
cd paper-ready
pnpm tauri build
```

## Test

Run backend tests from the repository root:

```bash
PYTHONPATH=paper-ready/backend pytest paper-ready/backend/tests
```

The backend can run without provider credentials by using deterministic fallback
steps and deterministic arXiv/Crossref metadata lookups. Configure `api_key`,
`llm_api_base_url`, and per-stage models in Settings to enable OpenAI-compatible
locator, evaluator, and summarizer calls. Local PDF text extraction uses
`pypdf`; Zotero export prepares a safe connector-style payload and can send it
to an optional `zotero_bridge_url`. The Tasks page can resolve locator
candidates, preview Zotero payloads before confirming export, run one queue
pass, or start a background worker; arXiv and discovered free PDFs are cached
under the local data directory when download succeeds. Zotero export defaults to
prepare-only mode; switch `zotero_export_mode` to `connector` to import through
Zotero Desktop Connector after the preview confirmation step.
