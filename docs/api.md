# PaperReady API

The desktop UI talks to a local FastAPI backend at `http://127.0.0.1:8765` by
default. Tauri exposes the same URL through the `backend_url` command.

## Health And Diagnostics

### `GET /health`

Returns backend readiness.

```json
{ "status": "ok" }
```

### `GET /debug/storage`

Returns the active SQLite path, task count, and current settings. This is for
local diagnostics only.

Current response also includes `data_dir` and `cache_size_bytes` so the Settings
UI can show local cache and storage diagnostics.

### `POST /debug/cache/clear`

Clears PaperReady-owned local cache files. Request:

```json
{ "mode": "failed" }
```

Allowed modes are `failed`, `exported`, and `all`. The cleanup only removes
files under PaperReady's configured data directory and does not touch Zotero.

## Pipeline

### `GET /pipeline`

Returns the ordered processing pipeline currently used by task processing.

Current response shape:

```json
[
  {
    "key": "locator",
    "label": "Paper Locator",
    "description": "Resolve raw input into paper metadata.",
    "mode": "automatic"
  }
]
```

The default pipeline is assembled from decoupled modules:

- `locator`
- `downloader`
- `parser`
- `evaluator`
- `summarizer`
- `zotero`

`locator` through `evaluator` are automatic resumable steps. `summarizer` is
manual by default, but the background worker can run it when `yolo_default` is
enabled. `zotero` is always triggered by explicit user confirmation.

## Worker

### `GET /worker`

Returns background worker status:

```json
{
  "running": false,
  "last_run_count": 0,
  "last_error": null
}
```

### `POST /worker/start`

Starts the FastAPI-process background queue worker. The worker polls the local
SQLite queue and runs automatic pipeline steps for runnable tasks. If global
`yolo_default` or the task-level YOLO override is enabled, tasks that reach
`Ready for report` continue through report generation until budget checks pause
them or they become ready for export.

### `POST /worker/stop`

Stops the background queue worker.

### `POST /worker/run-once`

Runs one background-worker pass over currently runnable tasks without keeping
the polling worker alive. This is useful for manual batch advancement from the
task list UI.

Worker execution uses settings-derived stage semaphores so locating/downloading,
parsing/evaluation, and YOLO summarization work respect configured concurrency
limits.

## Settings

### `GET /settings`

Returns persisted app settings, creating defaults on first use.

### `GET /settings/prompt-defaults`

Returns backend-owned default prompt templates for the prompt editor. Templates
are returned before variable rendering and may include tokens such as
`{{title}}`, `{{abstract}}`, `{{sections}}`, `{{references}}`,
`{{user_research_context}}`, and `{{value_recommendation}}`.

### `PUT /settings`

Replaces persisted settings. Important fields include:

- `research_interests`
- `research_tags`
- `default_start_page`
- `batch_budget`
- `daily_budget`
- `monthly_budget`
- `llm_api_base_url`
- `api_key`
- `locating_model`
- `evaluation_model`
- `summarization_model`
- `locating_concurrency`
- `evaluation_concurrency`
- `summarization_concurrency`
- `default_report_type`
- `yolo_default`
- `budget_overflow_behavior`
- `language_preference`
- `zotero_bridge_url`
- `zotero_connector_url`
- `zotero_export_mode`
- `zotero_default_collection`
- `zotero_include_pdf_by_default`
- `zotero_include_notes_by_default`
- `zotero_collection_mapping`
- `report_types`
- `prompt_templates`

LLM-backed locator, evaluator, and summarizer calls use `api_key`,
`llm_api_base_url`, and the relevant stage model. If no API key is configured
or the provider call fails, modules fall back to deterministic local behavior.
The locator uses model-managed web search when available to identify title or
URL inputs; if the model finds a credible arXiv match, PaperReady treats the
paper as resolved. Exact arXiv identifiers are also accepted as resolved even
when metadata enrichment fails. DOI inputs still use Crossref before local
fallback behavior.

## Tasks

### `POST /tasks`

Creates queued tasks from line-by-line input.

Request:

```json
{ "inputs": ["2401.12345", "10.1145/1234567", "A Paper Title"] }
```

Response: an array of `PaperTask` objects.

Tasks created by one request share `batch_id` and `batch_label`, which the Home
page uses to show recent import batches.

### `GET /tasks`

Lists durable queue tasks sorted by creation time.

### `DELETE /tasks/{task_id}`

Removes one task from the local queue and returns the remaining task list. This
is used by the article-level task center's remove action.

### `POST /tasks/{task_id}/process`

Advances one task through safe automatic workflow steps:

1. locate paper metadata
2. attach or derive PDF state
3. create parsed-paper representation
4. evaluate reading value

User-blocked and budget-paused tasks are not forced forward.

The downloader stores arXiv PDFs under the local data directory when download
succeeds. `PAPERREADY_DATA_DIR` overrides that directory; otherwise it is placed
next to the SQLite database under `data/`. Direct PDF URLs and landing pages
advertising `citation_pdf_url`, `application/pdf` links, or `.pdf` links are
treated as legal free PDF sources and cached the same way.

### `POST /tasks/{task_id}/retry`

Clears outputs from a selected pipeline step and immediately reruns automatic
processing. This is used for recoverable failures and manual retries.

Request:

```json
{ "step": "downloader" }
```

Allowed steps are `locator`, `downloader`, `parser`, `evaluator`, and
`summarizer`. If `step` is omitted, the backend infers a retry point from the
current task state.

### `POST /tasks/{task_id}/pdf`

Attaches or replaces a local PDF for a task whose paper identity is already
resolved. The path must point to an existing `.pdf` file. Successful attachment
marks the PDF as a user upload and clears parser, evaluation, and report outputs
so downstream steps can rerun against the replacement file.

Request:

```json
{ "path": "/Users/example/Papers/paper.pdf" }
```

### `POST /tasks/{task_id}/skip-pdf`

Continues a resolved task as metadata-only after the user chooses to skip PDF
download or parsing. This records `PDF unavailable`, creates a metadata-only
parsed representation, and advances evaluation so the task can still reach
report generation.

### `POST /tasks/{task_id}/resolve`

Resolves a task paused at `Needs disambiguation`. The user may choose a
candidate produced by the locator or provide edited paper metadata.

Candidate request:

```json
{ "candidate_index": 0 }
```

Edited metadata request:

```json
{
  "paper": {
    "title": "Chosen Paper",
    "authors": ["Ada Lovelace"],
    "doi": "10.1000/example",
    "urls": ["https://doi.org/10.1000/example"],
    "source_confidence": 1.0,
    "resolution_source": "user"
  }
}
```

Resolving a task clears downstream PDF, parser, evaluation, and report outputs
so the pipeline can continue from the selected identity.

### `POST /tasks/{task_id}/yolo`

Sets or clears the task-level YOLO override. `null` means the task follows the
global `yolo_default`; `true` and `false` explicitly override it.

Request:

```json
{ "enabled": true }
```

### `POST /tasks/process-all`

Advances every safe-to-run task once and returns the updated queue.

### `POST /tasks/{task_id}/override`

Applies a manual reading-value recommendation.

Request:

```json
{
  "value_recommendation": "Very Important",
  "rationale": "User override"
}
```

Allowed values are `Very Important`, `Brief Reading`, `Unrelated`, and
`Needs Review`.

## Reports

### `POST /tasks/{task_id}/report`

Generates a report for one task after estimating cost. If the estimate exceeds
`batch_budget`, the task moves to `Budget paused` and no report is created.

Request:

```json
{
  "report_type": "Quick Brief",
  "model_id": "gpt-4.1"
}
```

Both fields are optional. Defaults come from settings.

## Zotero Export

### `GET /zotero/status`

Probes Zotero Desktop Connector readiness without writing to the library.

Response:

```json
{
  "available": true,
  "connector_url": "http://127.0.0.1:23119",
  "selected": {
    "libraryID": 1,
    "collection": "..."
  },
  "error": null
}
```

### `POST /zotero/test-payload`

Returns a safe sample Zotero payload for Settings diagnostics. It does not write
to Zotero.

### `POST /export/zotero/preview`

Returns the connector-style Zotero payloads that would be exported, without
writing or sending them. The task-list UI uses this as the explicit confirmation
step before saving.

Request:

```json
{
  "task_ids": ["task_abc123"],
  "include_pdf": false,
  "include_notes": true,
  "category": "Brief Reading"
}
```

Response: preview payloads with title, tags, optional attachments, and optional
generated notes.

### `POST /export/zotero`

Records safe Zotero export intent for selected tasks. The current MVP skeleton
does not write to Zotero SQLite, delete items, or merge duplicates.

If `zotero_bridge_url` is configured, the backend sends a connector-style JSON
payload to that URL. Otherwise it prepares the payload locally and records the
task as exported.

Export behavior is controlled by `zotero_export_mode`:

- `prepare`: record the confirmed payload locally without writing Zotero.
- `bridge`: send the JSON payload to `zotero_bridge_url`.
- `connector`: import RIS through Zotero Desktop Connector at
  `zotero_connector_url`.

Requests may include `export_mode` to override the persisted Zotero export mode
for this confirmation only. Allowed values are `prepare`, `connector`, and
`bridge`.

Connector/bridge failures leave the task `Ready for export` so the user can fix
the connection and retry.

Request:

```json
{
  "task_ids": ["task_abc123"],
  "include_pdf": true,
  "include_notes": true,
  "category": "Brief Reading",
  "export_mode": "prepare"
}
```

Response: updated exported tasks.
