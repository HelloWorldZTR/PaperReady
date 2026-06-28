# PaperReady

PaperReady is a local-first Tauri desktop app for batch processing research
papers. The current implementation is an MVP skeleton with a Vue task-list UI
and a FastAPI backend backed by SQLite.

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

The backend currently implements demo-grade deterministic workflow steps. LLM
paper locating, richer PDF parsing, and real Zotero bridge calls are intentionally
behind service boundaries for the next milestones.
