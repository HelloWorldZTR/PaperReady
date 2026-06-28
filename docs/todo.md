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
- [ ] Run tests/build checks and record the milestone commit ID here.

## Backend Tasks

- [x] Define core data objects from the PRD: `PaperTask`, `PaperRecord`,
  `PdfRecord`, `ParsedPaper`, `EvaluationRecord`, and `ReportRecord`.
- [x] Store queue records and step outputs in SQLite.
- [x] Add API routes for health, settings, task creation, task listing, task
  processing, manual overrides, report generation, and Zotero export.
- [x] Keep user-blocked states out of automatic retries.
- [x] Record failure reasons and timestamps on every step.
- [x] Keep prompt templates in module-level variables outside functions.
- [ ] Add OpenAI-compatible client integration behind a service boundary.
- [ ] Add per-stage concurrency settings before enabling background workers.

## Frontend Tasks

- [x] Centralize user-facing UI strings for future i18n.
- [x] Add batch input controls for text lines and local PDF paths.
- [x] Render task rows with title/input, locator, PDF, parser, evaluation,
  report, cost, and next action columns.
- [ ] Add row actions for retry, override recommendation, report type/model
  selection, report generation, and export selection.
- [ ] Add settings controls for research interests, budget, API base URL, API
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
- Pending - Pipeline and macOS navigation.

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
