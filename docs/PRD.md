# PaperReady PRD

## 1. Product Positioning

PaperReady is a local-first desktop application for processing research papers in batches. It helps users turn loose paper inputs into a structured task list, resolve paper identity, obtain available PDFs, parse paper content, evaluate reading value, generate configurable reports, and export results to Zotero.

The product should feel like a download manager for papers. Each input becomes a visible task with clear status, recoverable failures, manual override points, and predictable cost controls.

The default product and documentation language is English. Future i18n should be supported by keeping user-facing copy centralized when implementation begins, but localization is not part of the v1 MVP.

## 2. V1 Goals and Non-Goals

### Goals

- Accept local PDFs and line-by-line paper identifiers such as DOI, title, URL, and arXiv ID.
- Resolve each input into a paper record, asking the user to disambiguate when resolution is uncertain or conflicting.
- Prefer arXiv when an arXiv version is available; v1 does not try to replace it with a published version.
- Download PDFs from user uploads, arXiv, and other legal free sources.
- Continue processing metadata even when a PDF cannot be acquired.
- Parse available PDFs into semantic paper sections.
- Evaluate whether a paper is worth deep reading based on metadata, abstract, parsed sections, and user research interests.
- Generate configurable LLM reports for selected papers.
- Export processed papers to Zotero with metadata, optional PDF attachments, tags, collections, and notes.
- Support resumable batch processing through a persistent local task queue.

### Non-Goals

- Deep Research page import.
- Browser extension support.
- Complex version-family management.
- Formal published-version preference or automatic replacement of arXiv versions.
- Advanced Zotero deduplication.
- Direct writes to Zotero SQLite.
- Paywall bypassing or non-open PDF acquisition.
- Fully automatic processing that silently exceeds the user’s usage budget.
- Full i18n implementation.

## 3. Core User Workflow

1. The user starts a batch by selecting one or more PDFs, pasting paper information line by line, or using both input methods.
2. PaperReady creates a task list. Each row represents one paper-like input and shows title, locating status, PDF status, parsing status, value judgment, report status, and next action.
3. The Paper Locator attempts to resolve every input. If it finds a confident match, the task advances automatically. If resolution fails or multiple plausible candidates conflict, the task pauses for user disambiguation.
4. The Paper Downloader attempts to attach a PDF. User-provided PDFs are trusted as the first source after identity verification. Otherwise the downloader tries arXiv and legal free sources. If no PDF is available, the task remains usable as metadata-only and the UI shows `PDF unavailable`.
5. The PDF Parser extracts semantic structure from available PDFs. If parsing fails, the task records the failure and still allows metadata-level evaluation.
6. The Paper Evaluator estimates whether the paper is worth deep reading. The user can accept, override, or defer the recommendation.
7. The user decides whether to generate a report, which report type to use, and which model to use. In YOLO mode, PaperReady may follow model recommendations automatically until estimated usage exceeds the configured budget.
8. When processing is complete, the user exports selected papers to Zotero categories such as `Very Important`, `Brief Reading`, and `Unrelated`.

## 4. System Modules

### 4.1 Paper Locator

Responsibility: convert user input into a resolved paper record.

Supported v1 inputs:

- DOI.
- DOI URL.
- arXiv ID or arXiv URL.
- Paper title.
- Paper URL.
- Local PDF metadata and first-page text.

Behavior:

- Normalize identifiers before lookup.
- Use an LLM with web search for demo-grade paper matching in v1.
- Prefer arXiv when an arXiv version is available.
- Return one confirmed paper when confidence is high.
- Return candidate options when multiple plausible papers exist.
- Mark the task as `Needs disambiguation` when the locator cannot safely choose.

Future versions may add deterministic academic APIs such as Crossref, OpenAlex, Semantic Scholar, and Unpaywall. These are not required for the first implementation.

### 4.2 Paper Downloader

Responsibility: obtain or attach a PDF for the resolved paper.

Source priority:

1. User-selected local PDF.
2. arXiv PDF.
3. Other legal free PDF sources found during locating.
4. Metadata-only fallback.

Behavior:

- Never attempt to bypass paywalls.
- Verify that a downloaded PDF appears to match the resolved paper when possible.
- Store PDF source, download status, and failure reason.
- If PDF acquisition fails, keep metadata and show `PDF unavailable` in the task list.

### 4.3 PDF Parser

Responsibility: convert a successful PDF into semantic paper content.

Expected output:

- Title and metadata cross-check.
- Abstract.
- Introduction.
- Method or approach sections.
- Experiments or evaluation sections.
- Conclusion.
- Figure captions.
- Table captions.
- References when available.
- Parse quality indicators.

The parser should produce a reusable intermediate representation so evaluation and summarization do not need to re-parse the PDF.

### 4.4 Paper Evaluator

Responsibility: estimate reading value before expensive report generation.

Inputs:

- Resolved metadata.
- Abstract.
- Parsed key sections such as introduction, method, experiments, and conclusion.
- User research interests.
- Parse quality and PDF availability.

Output:

- Value recommendation: `Very Important`, `Brief Reading`, `Unrelated`, or `Needs Review`.
- Short rationale.
- Confidence.
- Suggested next action.
- Suggested report type, if any.

The evaluator’s recommendation is advisory. The user can override it at any time.

### 4.5 Paper Summarizer

Responsibility: generate reports for papers selected by the user or by YOLO mode.

Behavior:

- Use a stronger configured LLM than the locator/evaluator by default.
- Respect report type settings.
- Respect per-stage model selection.
- Estimate cost before execution.
- Pause instead of exceeding the user’s configured budget.
- Save model, prompt version, report type, token usage, cost estimate, and generated output.

Default report types:

- `Quick Brief`: short summary, main contribution, relevance, and reading recommendation.
- `Standard Report`: problem, method, evidence, limitations, and relevance to user interests.
- `Detailed Report`: section-aware summary with method reconstruction, experiments, limitations, and evidence references.

### 4.6 Zotero Integration

Responsibility: export completed paper records to Zotero.

Behavior:

- Follow the interaction model of Zotero’s official web connector where possible: the user explicitly chooses what to save.
- Export metadata, optional PDF attachment, tags, collection assignment, and generated notes.
- Do not directly write to Zotero SQLite.
- Do not delete Zotero items.
- Do not merge suspected duplicates automatically.

Default export categories:

- `Very Important`.
- `Brief Reading`.
- `Unrelated`.
- `Needs Review`.

## 5. Task List UI and State Model

The main screen is a batch task list. It should be dense, scannable, and operational rather than promotional.

Each task row should include:

- Paper title or raw input.
- Locator status.
- PDF status.
- Parser status.
- Evaluation result.
- Report status.
- Estimated or actual cost.
- Next action.

Core task states:

- `Queued`: task was created but not started.
- `Locating`: resolving paper identity.
- `Needs disambiguation`: user must choose among candidates or edit input.
- `Located`: paper identity is resolved.
- `Downloading PDF`: looking for or attaching PDF.
- `PDF unavailable`: no legal free PDF was found.
- `PDF ready`: PDF is available.
- `Parsing`: extracting semantic sections.
- `Parse failed`: PDF exists but could not be parsed well enough.
- `Evaluating`: estimating reading value.
- `Needs review`: model recommendation or task state requires user confirmation.
- `Ready for report`: report can be generated.
- `Summarizing`: report generation is running.
- `Budget paused`: estimated cost would exceed the configured budget.
- `Ready for export`: Zotero export can run.
- `Exported`: Zotero export completed.
- `Failed`: unrecoverable error until user retries or edits input.

User actions:

- Add or replace PDF.
- Resolve identity ambiguity.
- Edit metadata.
- Retry failed step.
- Override value recommendation.
- Select report type.
- Select report model.
- Generate report.
- Enable or disable YOLO for selected tasks.
- Export selected tasks to Zotero.

## 6. Settings and User Configuration

PaperReady should expose settings that affect cost, model behavior, and report shape.

Required v1 settings:

- Research interests: free-form text or structured bullet list used by the evaluator and summarizer.
- Usage budget: per-batch and optional daily/monthly limits.
- LLM API base URL: supports OpenAI-compatible providers.
- API key storage: local secure storage where available.
- Stage models:
  - locating model.
  - evaluation model.
  - summarization model.
- Per-stage concurrency limits to reduce provider throttling or account bans.
- Report types with included sections.
- Editable prompt templates per report section.
- Default report type.
- YOLO mode default behavior.
- Budget overflow behavior: pause and ask for confirmation.
- Language preference placeholder for future i18n.

## 7. Data Objects

### PaperTask

Represents one input item in the batch queue.

Fields:

- `task_id`.
- `raw_input`.
- `input_type`.
- `status`.
- `paper_id`.
- `locator_status`.
- `pdf_status`.
- `parser_status`.
- `evaluation_status`.
- `report_status`.
- `next_action`.
- `created_at`.
- `updated_at`.

### PaperRecord

Represents resolved paper metadata.

Fields:

- `paper_id`.
- `title`.
- `authors`.
- `year`.
- `venue`.
- `doi`.
- `arxiv_id`.
- `urls`.
- `abstract`.
- `source_confidence`.
- `resolution_source`.
- `candidate_records` when disambiguation is required.

### PdfRecord

Represents a PDF file or failed PDF acquisition.

Fields:

- `pdf_id`.
- `paper_id`.
- `source_type`.
- `source_url`.
- `local_path`.
- `status`.
- `failure_reason`.
- `title_verified`.
- `created_at`.

### ParsedPaper

Represents semantic content extracted from a PDF.

Fields:

- `paper_id`.
- `sections`.
- `figures`.
- `tables`.
- `references`.
- `parse_quality`.
- `created_at`.

### EvaluationRecord

Represents the model’s reading-value recommendation.

Fields:

- `paper_id`.
- `value_recommendation`.
- `confidence`.
- `rationale`.
- `suggested_next_action`.
- `suggested_report_type`.
- `model_id`.
- `prompt_version`.
- `created_at`.

### ReportRecord

Represents a generated report.

Fields:

- `report_id`.
- `paper_id`.
- `report_type`.
- `sections`.
- `model_id`.
- `prompt_version`.
- `input_token_estimate`.
- `output_token_estimate`.
- `estimated_cost`.
- `actual_usage` when available.
- `created_at`.

## 8. Backend Queue and Resumability

PaperReady uses a local persistent queue managed by the backend.

Technical shape:

- Frontend: Tauri desktop shell with a web UI.
- Backend: FastAPI subprocess managed by the desktop app.
- Storage: SQLite or an equivalent lightweight local database.
- LLM client: Python `openai` package with configurable API base URL.
- Queue: local task table with status, retries, timestamps, and step outputs.

Queue requirements:

- Each module step writes its result before the next step starts.
- App restart should resume incomplete tasks from the last durable step.
- Failed steps should preserve failure reason and allow retry.
- User-blocked states should not be retried automatically.
- Cost estimates should be recorded before expensive LLM calls.
- The backend should enforce concurrency limits per stage.

The Tauri layer owns desktop lifecycle and UI. The FastAPI backend owns task execution, storage, PDF processing, LLM calls, and Zotero bridge calls.

## 9. Zotero Integration

Zotero is the long-term library target, not the internal workflow engine.

V1 integration should:

- Let users choose which completed tasks to export.
- Create or update Zotero items through a supported bridge or API approach.
- Attach PDFs only when available.
- Add generated notes when selected.
- Apply category collections or tags such as `Very Important`, `Brief Reading`, `Unrelated`, and `Needs Review`.
- Preserve PaperReady task records locally after export.

V1 integration should not:

- Directly modify `zotero.sqlite`.
- Delete Zotero items.
- Automatically merge duplicates.
- Overwrite user-written Zotero notes without confirmation.
- Treat Zotero collections as the source of truth for local task state.

## 10. MVP Acceptance Criteria

The MVP is acceptable when:

- A user can input multiple paper titles, URLs, DOIs, arXiv IDs, and local PDFs.
- Each input appears as a task row with clear status.
- The system can resolve straightforward arXiv and DOI-like inputs.
- Ambiguous locating results pause for user disambiguation.
- PDF download succeeds from arXiv when available.
- PDF download failure leaves a metadata-only task marked `PDF unavailable`.
- Available PDFs are parsed into semantic sections.
- The evaluator produces a value recommendation using research interests.
- The user can override recommendations and choose report settings.
- The summarizer generates at least one configurable report type.
- Budget overflow pauses processing before the expensive call is made.
- Queue state survives app restart.
- Selected completed papers can be exported to Zotero categories.
- The PRD, default UI language, and implementation-facing names are English.

## 11. Future Roadmap

Post-v1 capabilities:

- Deep Research text import.
- Deep Research page or share-link import.
- Browser extension.
- Deterministic academic metadata APIs.
- Unpaywall integration.
- Advanced Zotero duplicate detection.
- Version-family management across arXiv, conference, journal, and OpenReview versions.
- Published-version preference policies.
- Cross-paper comparison reports.
- Project-level literature maps.
- Learning user preferences from existing Zotero libraries.
- Full i18n with localized UI strings, report templates, and settings labels.
