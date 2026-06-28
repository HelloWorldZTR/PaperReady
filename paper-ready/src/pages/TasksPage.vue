<script setup>
import { computed, reactive } from "vue";
import { STRINGS } from "../strings";

const props = defineProps({
  loading: Boolean,
  pipeline: { type: Array, required: true },
  settings: { type: Object, required: true },
  selectedTaskIds: { type: Object, required: true },
  tasks: { type: Array, required: true },
  workerStatus: { type: Object, required: true },
  zoteroStatus: { type: Object, required: true },
  exportPreview: { type: Array, required: true },
  exportOptions: { type: Object, required: true },
});
const emit = defineEmits([
  "attach-pdf",
  "cancel-export-preview",
  "confirm-export-selected",
  "generate-report",
  "override-recommendation",
  "preview-export-selected",
  "probe-zotero",
  "process-all",
  "refresh",
  "resolve-task",
  "retry-task",
  "run-worker-once",
  "set-selected-yolo",
  "set-worker-running",
  "toggle-selection",
]);

const rowChoices = reactive({});
const selectedCount = computed(() => props.selectedTaskIds.size);
const totalCost = computed(() =>
  props.tasks.reduce((sum, task) => sum + (task.estimated_cost || 0), 0).toFixed(4),
);
const reportTypes = computed(() => Object.keys(props.settings.report_types || {}));
const retrySteps = computed(() => props.pipeline.filter((step) => step.key !== "zotero"));

/** Return mutable row choices with sensible defaults. */
function choices(task) {
  if (!rowChoices[task.task_id]) {
    rowChoices[task.task_id] = {
      modelId: props.settings.summarization_model,
      reportType: task.evaluation?.suggested_report_type || props.settings.default_report_type,
      retryStep: "evaluator",
      editingMetadata: false,
      metadataDraft: null,
      pdfPath: "",
    };
  }
  return rowChoices[task.task_id];
}

/** Return true when a task can generate a report from the table. */
function canGenerate(task) {
  return task.status === "Ready for report" || task.status === "Needs review";
}

/** Return generated report sections in display order. */
function reportSections(task) {
  return Object.entries(task.report?.sections || {});
}

/** Return candidate records for a disambiguation task. */
function candidates(task) {
  return task.paper?.candidate_records || [];
}

/** Return compact text for task-level YOLO state. */
function yoloLabel(task) {
  if (task.yolo_enabled === true) {
    return "YOLO on";
  }
  if (task.yolo_enabled === false) {
    return "YOLO off";
  }
  return props.settings.yolo_default ? "YOLO default on" : "YOLO default off";
}

/** Open the inline metadata editor for one task row. */
function startEditMetadata(task) {
  const paper = task.paper || {};
  choices(task).metadataDraft = {
    title: paper.title || task.raw_input,
    authors: (paper.authors || []).join(", "),
    year: paper.year || "",
    venue: paper.venue || "",
    doi: paper.doi || "",
    arxiv_id: paper.arxiv_id || "",
    urls: (paper.urls || []).join("\n"),
    abstract: paper.abstract || "",
  };
  choices(task).editingMetadata = true;
}

/** Convert the row editor fields into a PaperRecord-shaped payload. */
function buildEditedPaper(task) {
  const draft = choices(task).metadataDraft || {};
  const year = Number.parseInt(draft.year, 10);
  return {
    paper_id: task.paper?.paper_id,
    title: (draft.title || task.raw_input).trim(),
    authors: (draft.authors || "")
      .split(",")
      .map((author) => author.trim())
      .filter(Boolean),
    year: Number.isNaN(year) ? null : year,
    venue: draft.venue || null,
    doi: draft.doi || null,
    arxiv_id: draft.arxiv_id || null,
    urls: (draft.urls || "")
      .split(/\n|,/)
      .map((url) => url.trim())
      .filter(Boolean),
    abstract: draft.abstract || null,
    source_confidence: 1,
    resolution_source: "user_edit",
    candidate_records: [],
  };
}

/** Save user-edited metadata through the task resolution API. */
function saveMetadata(task) {
  emit("resolve-task", task, buildEditedPaper(task));
  choices(task).editingMetadata = false;
}
</script>

<template>
  <section class="page-card">
    <header class="page-header">
      <div>
        <h2>{{ STRINGS.tasks.title }}</h2>
        <p>
          <strong>{{ tasks.length }}</strong> tasks · {{ selectedCount }} selected · ${{
            totalCost
          }} estimated · worker {{ workerStatus.running ? "running" : "idle" }}
        </p>
      </div>
      <div class="actions">
        <button type="button" :disabled="loading" @click="emit('refresh')">
          {{ STRINGS.tasks.refresh }}
        </button>
        <button type="button" :disabled="loading" @click="emit('process-all')">
          {{ STRINGS.tasks.processAll }}
        </button>
        <button type="button" :disabled="loading" @click="emit('run-worker-once')">
          Run once
        </button>
        <button
          type="button"
          :disabled="loading || selectedCount === 0"
          @click="emit('set-selected-yolo', true)"
        >
          YOLO on
        </button>
        <button
          type="button"
          :disabled="loading || selectedCount === 0"
          @click="emit('set-selected-yolo', false)"
        >
          YOLO off
        </button>
        <button
          type="button"
          :disabled="loading"
          @click="emit('set-worker-running', !workerStatus.running)"
        >
          {{ workerStatus.running ? "Stop worker" : "Start worker" }}
        </button>
        <button
          type="button"
          class="primary"
          :disabled="loading || selectedCount === 0"
          @click="emit('preview-export-selected', exportOptions)"
        >
          {{ STRINGS.tasks.export }}
        </button>
      </div>
    </header>

    <section v-if="exportPreview.length" class="export-preview">
      <div class="export-preview-header">
        <div>
          <strong>Zotero export preview</strong>
          <span>
            {{ exportPreview.length }} items · mode {{ settings.zotero_export_mode }} ·
            {{ zoteroStatus.available ? "connector ready" : "connector not ready" }}
          </span>
        </div>
        <div class="actions">
          <button type="button" @click="emit('probe-zotero')">Probe Zotero</button>
          <label class="inline-check">
            <input
              :checked="exportOptions.include_pdf"
              type="checkbox"
              @change="
                emit('preview-export-selected', {
                  ...exportOptions,
                  include_pdf: $event.target.checked,
                })
              "
            />
            PDF
          </label>
          <label class="inline-check">
            <input
              :checked="exportOptions.include_notes"
              type="checkbox"
              @change="
                emit('preview-export-selected', {
                  ...exportOptions,
                  include_notes: $event.target.checked,
                })
              "
            />
            Notes
          </label>
          <button type="button" @click="emit('cancel-export-preview')">Cancel</button>
          <button type="button" class="primary" @click="emit('confirm-export-selected')">
            Confirm export
          </button>
        </div>
      </div>
      <div class="preview-items">
        <article v-for="item in exportPreview" :key="item.task_id" class="preview-item">
          <strong>{{ item.title }}</strong>
          <span>{{ item.tags.join(', ') }}</span>
          <small>
            {{ item.attachments.length }} attachments · {{ item.notes.length }} notes
          </small>
        </article>
      </div>
    </section>

    <div v-if="tasks.length === 0" class="empty">{{ STRINGS.tasks.empty }}</div>

    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Paper</th>
            <th>Locator</th>
            <th>PDF</th>
            <th>Parser</th>
            <th>Value</th>
            <th>Report</th>
            <th>Cost</th>
            <th>Controls</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.task_id">
            <td>
              <input
                type="checkbox"
                :checked="selectedTaskIds.has(task.task_id)"
                @change="emit('toggle-selection', task.task_id)"
              />
            </td>
            <td class="paper-cell">
              <strong>{{ task.paper?.title || task.raw_input }}</strong>
              <small>{{ task.input_type }} · {{ task.status }} · {{ yoloLabel(task) }}</small>
              <button
                type="button"
                class="link-button"
                :disabled="loading"
                @click="startEditMetadata(task)"
              >
                Edit metadata
              </button>
              <div v-if="choices(task).editingMetadata" class="metadata-editor">
                <label>
                  Title
                  <input v-model="choices(task).metadataDraft.title" type="text" />
                </label>
                <label>
                  Authors
                  <input
                    v-model="choices(task).metadataDraft.authors"
                    type="text"
                    placeholder="Comma-separated names"
                  />
                </label>
                <label>
                  Year
                  <input v-model="choices(task).metadataDraft.year" type="number" />
                </label>
                <label>
                  Venue
                  <input v-model="choices(task).metadataDraft.venue" type="text" />
                </label>
                <label>
                  DOI
                  <input v-model="choices(task).metadataDraft.doi" type="text" />
                </label>
                <label>
                  arXiv ID
                  <input v-model="choices(task).metadataDraft.arxiv_id" type="text" />
                </label>
                <label class="wide">
                  URLs
                  <textarea v-model="choices(task).metadataDraft.urls" rows="2"></textarea>
                </label>
                <label class="wide">
                  Abstract
                  <textarea v-model="choices(task).metadataDraft.abstract" rows="3"></textarea>
                </label>
                <div class="metadata-actions">
                  <button type="button" class="primary" @click="saveMetadata(task)">
                    Save
                  </button>
                  <button
                    type="button"
                    @click="choices(task).editingMetadata = false"
                  >
                    Cancel
                  </button>
                </div>
              </div>
              <div v-if="candidates(task).length" class="candidate-list">
                <div
                  v-for="(candidate, index) in candidates(task)"
                  :key="`${task.task_id}-${index}`"
                  class="candidate-row"
                >
                  <span>
                    {{ candidate.title }}
                    <small>
                      {{ candidate.doi || candidate.arxiv_id || candidate.resolution_source }}
                    </small>
                  </span>
                  <button
                    type="button"
                    :disabled="loading"
                    @click="emit('resolve-task', task, index)"
                  >
                    Choose
                  </button>
                </div>
              </div>
            </td>
            <td>{{ task.locator_status }}</td>
            <td>{{ task.pdf_status }}</td>
            <td>{{ task.parser_status }}</td>
            <td>
              <span class="badge">{{ task.evaluation_status }}</span>
              <div class="mini-actions">
                <button
                  type="button"
                  @click="emit('override-recommendation', task, 'Very Important')"
                >
                  Very
                </button>
                <button
                  type="button"
                  @click="emit('override-recommendation', task, 'Brief Reading')"
                >
                  Brief
                </button>
                <button type="button" @click="emit('override-recommendation', task, 'Unrelated')">
                  Skip
                </button>
              </div>
            </td>
            <td class="report-cell">
              <span>{{ task.report_status }}</span>
              <select v-model="choices(task).reportType">
                <option v-for="type in reportTypes" :key="type">{{ type }}</option>
              </select>
              <input v-model="choices(task).modelId" type="text" placeholder="Report model" />
              <details v-if="task.report" class="report-preview">
                <summary>{{ task.report.report_type }}</summary>
                <section
                  v-for="[heading, content] in reportSections(task)"
                  :key="`${task.task_id}-${heading}`"
                >
                  <strong>{{ heading }}</strong>
                  <p>{{ content }}</p>
                </section>
              </details>
            </td>
            <td>${{ (task.estimated_cost || 0).toFixed(4) }}</td>
            <td class="next-cell">
              <span>{{ task.next_action }}</span>
              <button
                v-if="canGenerate(task)"
                type="button"
                @click="emit('generate-report', task, choices(task))"
              >
                {{ STRINGS.tasks.generate }}
              </button>
              <div class="retry-controls">
                <select v-model="choices(task).retryStep">
                  <option v-for="step in retrySteps" :key="step.key" :value="step.key">
                    Retry {{ step.label }}
                  </option>
                </select>
                <button
                  type="button"
                  :disabled="loading"
                  @click="emit('retry-task', task, choices(task).retryStep)"
                >
                  Retry
                </button>
              </div>
              <div class="pdf-controls">
                <input
                  v-model="choices(task).pdfPath"
                  type="text"
                  placeholder="Local PDF path"
                />
                <button
                  type="button"
                  :disabled="loading || !choices(task).pdfPath"
                  @click="emit('attach-pdf', task, choices(task).pdfPath)"
                >
                  Attach PDF
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
