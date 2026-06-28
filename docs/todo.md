# PaperReady Todo

This file tracks implementation work derived from `docs/PRD.md`. Keep it up to
date as the handoff source for future implementation.

## Current Milestone: Local-First MVP Skeleton

- [x] Convert the PRD into an implementation task list.
- [x] Create a FastAPI backend with a durable SQLite task queue.
- [x] Add task creation from line-by-line DOI, arXiv ID, URL, title, and local
  PDF path inputs.
- [x] Implement demo-grade paper locating for straightforward arXiv and DOI-like
  inputs, with `Needs disambiguation` as the safe fallback.
- [x] Implement PDF attachment/download state handling with arXiv PDF URL
  detection and metadata-only fallback.
- [x] Implement a reusable parsed-paper intermediate representation.
- [x] Implement metadata/section-based reading value evaluation.
- [x] Implement configurable report generation with budget checks.
- [x] Implement Zotero export as a safe bridge stub that records export intent
  without writing to Zotero SQLite.
- [x] Replace the starter Vue screen with a dense task-list UI.
- [x] Document backend APIs in `docs/api.md`.
- [x] Document run/build steps in `paper-ready/README.md`.
- [x] Add pytest coverage for important backend functionality.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: Pipeline And macOS Navigation

- [x] Split workflow implementation into decoupled backend modules:
  locator, downloader, parser, evaluator, summarizer, and Zotero bridge.
- [x] Add a `PaperPipeline` subsystem that composes ordered idempotent steps.
- [x] Keep `services.py` as a compatibility facade over the pipeline/modules.
- [x] Expose the backend pipeline shape through `GET /pipeline`.
- [x] Split the frontend into home, task list, and settings subpages.
- [x] Keep the Home page focused on one batch input box and one PDF drag box.
- [x] Move task list and settings controls to their own pages.
- [x] Add a macOS-style custom title bar and sidebar navigation.
- [x] Update Tauri window sizing and disable native decorations for the custom
  title bar.
- [x] Move frontend API helpers, UI strings, and global styles into separate
  files.
- [x] Add tests for the published pipeline shape.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: Task Controls And Settings Coverage

- [x] Expand pipeline description to include automatic modules and manual
  summarizer/Zotero modules.
- [x] Add `POST /tasks/{task_id}/retry` to reset from a selected pipeline step.
- [x] Add backend tests for retry behavior and full pipeline descriptors.
- [x] Add per-row retry controls to the task list page.
- [x] Add per-row report type and report model controls.
- [x] Expand settings with API key, daily/monthly budgets, concurrency, YOLO
  default, budget overflow behavior, language placeholder, report types JSON,
  and prompt templates JSON.
- [x] Update `docs/api.md` for pipeline modes, retry, and expanded settings.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: LLM/PDF/Zotero Service Boundaries

- [x] Add an OpenAI-compatible LLM client boundary using settings for API key,
  API base URL, and per-stage models.
- [x] Wire locator, evaluator, and summarizer modules through the LLM boundary
  with deterministic fallback when no key is configured or provider calls fail.
- [x] Move prompt text into module-level prompt variables.
- [x] Add token estimation for report budget checks using actual report input
  text plus report-type floor estimates.
- [x] Add `pypdf`-based local PDF text extraction for user-provided PDFs.
- [x] Add semantic section extraction from PDF text for abstract, introduction,
  method, experiments/evaluation, conclusion, and references.
- [x] Build safe Zotero connector-style export payloads with optional PDF
  attachments and generated report notes.
- [x] Add optional `zotero_bridge_url` setting for HTTP bridge export without
  direct SQLite writes.
- [x] Add tests for semantic section extraction and Zotero export payloads.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: Background Worker And PDF Cache

- [x] Add a FastAPI-process background worker manager for the durable queue.
- [x] Add worker APIs for status, start, stop, and run-once.
- [x] Use settings-derived stage semaphores for automatic pipeline concurrency.
- [x] Stop the worker during FastAPI shutdown.
- [x] Add task-list controls for run-once, start worker, and stop worker.
- [x] Add local data directory support through `PAPERREADY_DATA_DIR`.
- [x] Download arXiv PDFs into a local `data/pdfs` cache when network download
  succeeds.
- [x] Keep legal source URL metadata and failure reason when local PDF download
  is unavailable.
- [x] Add tests for worker run-once and cached PDF paths without real network
  access.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: Metadata Lookup And Disambiguation

- [x] Add deterministic metadata lookup helpers for Crossref DOI/title search
  and arXiv Atom metadata.
- [x] Let locator prefer deterministic arXiv/DOI metadata before LLM/demo
  fallback.
- [x] Pause title conflicts as `Needs disambiguation` with candidate records.
- [x] Add `POST /tasks/{task_id}/resolve` for candidate or edited metadata
  resolution.
- [x] Clear downstream PDF/parser/evaluation/report outputs when identity is
  manually resolved.
- [x] Show locator candidates in the task-list UI with per-candidate Choose
  actions.
- [x] Add tests for deterministic DOI metadata, candidate pause, resolve API,
  and disambiguation UI data flow.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: URL PDF Discovery And Zotero Preview

- [x] Classify HTTP(S) PDF links as URL inputs while keeping arXiv/DOI URLs
  normalized as arXiv/DOI inputs.
- [x] Add URL fallback metadata so generic paper URLs can enter the pipeline.
- [x] Download/cache direct PDF URLs as legal free PDF sources.
- [x] Discover landing-page PDF links from `citation_pdf_url`, application/pdf
  links, and `.pdf` anchors.
- [x] Add `POST /export/zotero/preview` for explicit export confirmation.
- [x] Let export preview and confirmed export respect include-PDF and
  include-notes toggles.
- [x] Add a task-list Zotero export preview panel with PDF/notes toggles,
  cancel, and confirm export controls.
- [x] Add tests for direct PDF URLs, discovered PDF URLs, and export preview
  toggles.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: Zotero Connector Confirmation Flow

- [x] Add Zotero connector settings for connector URL and export mode.
- [x] Add `GET /zotero/status` to probe connector ping and selected collection
  without writing to Zotero.
- [x] Add connector export mode that imports RIS through Zotero Desktop
  Connector after user confirmation.
- [x] Keep `prepare` as the default export mode to avoid accidental library
  writes.
- [x] Keep bridge/connector failures recoverable by leaving tasks ready for
  export instead of marking them completed.
- [x] Surface connector readiness in the task-list export preview with a
  manual Probe Zotero action.
- [x] Add tests for connector probe, connector import success, and status API.
- [x] Run tests/build checks and record the milestone commit ID here.

## Current Milestone: YOLO Worker Report Generation

- [x] Let the background worker treat `Ready for report` tasks as runnable only
  when `yolo_default` is enabled.
- [x] Generate reports from the worker using the suggested report type or the
  configured default report type.
- [x] Apply the summarization concurrency limiter to worker-generated reports.
- [x] Keep budget checks in the summarizer so YOLO report generation pauses
  instead of exceeding the configured batch budget.
- [x] Document YOLO worker behavior in `docs/api.md` and `paper-ready/README.md`.
- [x] Add API coverage for YOLO worker report generation.
- [x] Run tests/build checks and record the milestone commit ID here.

## Backend Tasks

- [x] Define core data objects from the PRD: `PaperTask`, `PaperRecord`,
  `PdfRecord`, `ParsedPaper`, `EvaluationRecord`, and `ReportRecord`.
- [x] Store queue records and step outputs in SQLite.
- [x] Add API routes for health, settings, task creation, task listing, task
  processing, manual overrides, report generation, and Zotero export.
- [x] Keep user-blocked states out of automatic retries.
- [x] Record failure reasons and timestamps on every step.
- [x] Keep prompt templates in module-level variables outside functions.
- [x] Add OpenAI-compatible client integration behind a service boundary.
- [x] Add per-stage concurrency settings before enabling background workers.

## Frontend Tasks

- [x] Centralize user-facing UI strings for future i18n.
- [x] Add batch input controls for text lines and local PDF paths.
- [x] Render task rows with title/input, locator, PDF, parser, evaluation,
  report, cost, and next action columns.
- [x] Add row actions for retry, override recommendation, report type/model
  selection, report generation, and export selection.
- [x] Add settings controls for research interests, budget, API base URL, API
  key, stage models, concurrency, report types, prompt templates, YOLO default,
  budget overflow behavior, and language placeholder.
- [x] Surface loading, error, empty, and metadata-only states clearly.

## Documentation And Quality

- [x] Keep `docs/PRD.md` unchanged.
- [x] Keep modified source files below 500 lines unless they are stylesheets or
  prompt-heavy files.
- [x] Add brief docstrings to primary Python functions.
- [x] Add doc comments to primary Rust commands.
- [x] Use pytest in the `generic` conda environment for backend tests.
- [x] Update `requirements.txt` whenever Python dependencies change.
- [x] Commit each major milestone and record the commit hash below.

## Milestone Commits

- `072e323` - Implement local-first MVP skeleton.
- `bec90db` - Refactor pipeline and macOS navigation.
- `fb7f0dc` - Add task retry and settings controls.
- `0892dcb` - Add LLM PDF and Zotero service boundaries.
- `68df58e` - Add background worker and PDF cache.
- `705cb9d` - Add metadata lookup and disambiguation.
- `0552bfe` - Add URL PDF discovery and export preview.
- `8259ee1` - Add Zotero connector confirmation flow.
- `7f61144` - Add YOLO worker report generation.

## Verification

- `PYTHONPATH=paper-ready/backend conda run -n generic python -m pytest paper-ready/backend/tests`
- `cd paper-ready && pnpm build`
- `cd paper-ready/src-tauri && cargo check`

## Scratch Notes

- Default product language and implementation-facing names are English.
- V1 should prefer arXiv when an arXiv version is available and should not try
  to replace it with a published version.
- PDF acquisition must never bypass paywalls. Failure should leave a usable
  metadata-only task marked `PDF unavailable`.
- Zotero integration must not directly write to `zotero.sqlite`, delete items,
  or automatically merge suspected duplicates.
- Expensive LLM calls must be preceded by cost estimates and pause before
  exceeding the configured budget.
