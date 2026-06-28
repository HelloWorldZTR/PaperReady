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

## Settings

### `GET /settings`

Returns persisted app settings, creating defaults on first use.

### `PUT /settings`

Replaces persisted settings. Important fields include:

- `research_interests`
- `batch_budget`
- `llm_api_base_url`
- `locating_model`
- `evaluation_model`
- `summarization_model`
- `default_report_type`
- `report_types`
- `prompt_templates`

## Tasks

### `POST /tasks`

Creates queued tasks from line-by-line input.

Request:

```json
{ "inputs": ["2401.12345", "10.1145/1234567", "A Paper Title"] }
```

Response: an array of `PaperTask` objects.

### `GET /tasks`

Lists durable queue tasks sorted by creation time.

### `POST /tasks/{task_id}/process`

Advances one task through safe automatic workflow steps:

1. locate paper metadata
2. attach or derive PDF state
3. create parsed-paper representation
4. evaluate reading value

User-blocked and budget-paused tasks are not forced forward.

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

### `POST /export/zotero`

Records safe Zotero export intent for selected tasks. The current MVP skeleton
does not write to Zotero SQLite, delete items, or merge duplicates.

Request:

```json
{
  "task_ids": ["task_abc123"],
  "include_pdf": true,
  "include_notes": true,
  "category": "Brief Reading"
}
```

Response: updated exported tasks.

