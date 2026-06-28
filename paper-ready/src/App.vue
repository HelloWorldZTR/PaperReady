<script setup>
import { computed, onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const STRINGS = {
  appName: "PaperReady",
  tagline: "Local-first paper batch queue",
  addTasks: "Add tasks",
  processAll: "Process all",
  refresh: "Refresh",
  generate: "Report",
  export: "Export",
  empty: "No tasks yet. Add paper titles, DOI, arXiv IDs, URLs, or PDF paths.",
};

const fallbackBackendUrl = "http://127.0.0.1:8765";
const backendUrl = ref(fallbackBackendUrl);
const batchInput = ref("2401.12345\n10.1145/1234567\nA Useful Paper Title");
const tasks = ref([]);
const selectedTaskIds = ref(new Set());
const loading = ref(false);
const errorMessage = ref("");
const settings = ref({
  research_interests: "",
  batch_budget: 3,
  llm_api_base_url: "https://api.openai.com/v1",
  locating_model: "gpt-4.1-mini",
  evaluation_model: "gpt-4.1-mini",
  summarization_model: "gpt-4.1",
  default_report_type: "Quick Brief",
});

const selectedCount = computed(() => selectedTaskIds.value.size);
const totalCost = computed(() =>
  tasks.value.reduce((sum, task) => sum + (task.estimated_cost || 0), 0).toFixed(4),
);

/** Call the local backend and surface failures in the UI. */
async function api(path, options = {}) {
  const response = await fetch(`${backendUrl.value}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

/** Load backend endpoint, settings, and the current queue. */
async function initialize() {
  loading.value = true;
  try {
    backendUrl.value = await invoke("backend_url");
  } catch {
    backendUrl.value = fallbackBackendUrl;
  }
  try {
    settings.value = await api("/settings");
    await refreshTasks();
  } catch (error) {
    errorMessage.value = `Backend unavailable: ${error.message}`;
  } finally {
    loading.value = false;
  }
}

/** Refresh queue rows from durable backend state. */
async function refreshTasks() {
  tasks.value = await api("/tasks");
}

/** Persist settings used by evaluation, budget checks, and model choices. */
async function saveSettings() {
  loading.value = true;
  try {
    settings.value = await api("/settings", {
      method: "PUT",
      body: JSON.stringify(settings.value),
    });
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Create queue tasks from line-by-line batch input. */
async function addTasks() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const inputs = batchInput.value.split("\n").map((line) => line.trim());
    await api("/tasks", {
      method: "POST",
      body: JSON.stringify({ inputs }),
    });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Advance every safe task through the demo workflow. */
async function processAll() {
  loading.value = true;
  errorMessage.value = "";
  try {
    tasks.value = await api("/tasks/process-all", { method: "POST" });
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Generate the selected task's configured report. */
async function generateReport(task) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api(`/tasks/${task.task_id}/report`, {
      method: "POST",
      body: JSON.stringify({
        report_type: task.evaluation?.suggested_report_type || settings.value.default_report_type,
        model_id: settings.value.summarization_model,
      }),
    });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Apply a user recommendation override to one row. */
async function overrideRecommendation(task, value) {
  loading.value = true;
  try {
    await api(`/tasks/${task.task_id}/override`, {
      method: "POST",
      body: JSON.stringify({ value_recommendation: value, rationale: "User override" }),
    });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Record Zotero export intent for selected rows. */
async function exportSelected() {
  loading.value = true;
  errorMessage.value = "";
  try {
    tasks.value = await api("/export/zotero", {
      method: "POST",
      body: JSON.stringify({ task_ids: [...selectedTaskIds.value] }),
    });
    selectedTaskIds.value = new Set();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Toggle a task row in the export selection. */
function toggleSelection(taskId) {
  const next = new Set(selectedTaskIds.value);
  next.has(taskId) ? next.delete(taskId) : next.add(taskId);
  selectedTaskIds.value = next;
}

onMounted(initialize);
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>{{ STRINGS.appName }}</h1>
        <p>{{ STRINGS.tagline }}</p>
      </div>
      <div class="actions">
        <button type="button" @click="refreshTasks" :disabled="loading">
          {{ STRINGS.refresh }}
        </button>
        <button type="button" class="primary" @click="processAll" :disabled="loading">
          {{ STRINGS.processAll }}
        </button>
      </div>
    </header>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

    <section class="workspace">
      <aside class="sidebar">
        <section class="panel">
          <h2>Batch Input</h2>
          <textarea v-model="batchInput" rows="8" />
          <button type="button" class="primary full" @click="addTasks" :disabled="loading">
            {{ STRINGS.addTasks }}
          </button>
        </section>

        <section class="panel">
          <h2>Settings</h2>
          <label>
            Research interests
            <textarea v-model="settings.research_interests" rows="4" />
          </label>
          <label>
            Batch budget
            <input v-model.number="settings.batch_budget" type="number" min="0" step="0.01" />
          </label>
          <label>
            API base URL
            <input v-model="settings.llm_api_base_url" type="text" />
          </label>
          <label>
            Locator model
            <input v-model="settings.locating_model" type="text" />
          </label>
          <label>
            Evaluation model
            <input v-model="settings.evaluation_model" type="text" />
          </label>
          <label>
            Summary model
            <input v-model="settings.summarization_model" type="text" />
          </label>
          <label>
            Default report
            <select v-model="settings.default_report_type">
              <option>Quick Brief</option>
              <option>Standard Report</option>
              <option>Detailed Report</option>
            </select>
          </label>
          <button type="button" class="full" @click="saveSettings" :disabled="loading">
            Save settings
          </button>
        </section>
      </aside>

      <section class="queue">
        <div class="queue-summary">
          <div>
            <strong>{{ tasks.length }}</strong> tasks
            <span>{{ selectedCount }} selected</span>
            <span>${{ totalCost }} estimated</span>
          </div>
          <button
            type="button"
            @click="exportSelected"
            :disabled="loading || selectedCount === 0"
          >
            {{ STRINGS.export }}
          </button>
        </div>

        <div v-if="tasks.length === 0" class="empty">{{ STRINGS.empty }}</div>

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
                <th>Next Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.task_id">
                <td>
                  <input
                    type="checkbox"
                    :checked="selectedTaskIds.has(task.task_id)"
                    @change="toggleSelection(task.task_id)"
                  />
                </td>
                <td class="paper-cell">
                  <strong>{{ task.paper?.title || task.raw_input }}</strong>
                  <small>{{ task.input_type }} | {{ task.status }}</small>
                </td>
                <td>{{ task.locator_status }}</td>
                <td>{{ task.pdf_status }}</td>
                <td>{{ task.parser_status }}</td>
                <td>
                  <span class="badge">{{ task.evaluation_status }}</span>
                  <div class="mini-actions">
                    <button type="button" @click="overrideRecommendation(task, 'Very Important')">
                      Very
                    </button>
                    <button type="button" @click="overrideRecommendation(task, 'Brief Reading')">
                      Brief
                    </button>
                    <button type="button" @click="overrideRecommendation(task, 'Unrelated')">
                      Skip
                    </button>
                  </div>
                </td>
                <td>{{ task.report_status }}</td>
                <td>${{ (task.estimated_cost || 0).toFixed(4) }}</td>
                <td class="next-cell">
                  <span>{{ task.next_action }}</span>
                  <button
                    v-if="task.status === 'Ready for report' || task.status === 'Needs review'"
                    type="button"
                    @click="generateReport(task)"
                  >
                    {{ STRINGS.generate }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </main>
</template>

<style>
:root {
  color: #17202a;
  background: #f5f7fa;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  font-size: 15px;
  line-height: 1.4;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  border: 1px solid #c8d0da;
  border-radius: 6px;
  background: #ffffff;
  color: #17202a;
  cursor: pointer;
  min-height: 34px;
  padding: 0 12px;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

button.primary {
  background: #1455d9;
  border-color: #1455d9;
  color: #ffffff;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid #c8d0da;
  border-radius: 6px;
  background: #ffffff;
  color: #17202a;
  padding: 8px 10px;
}

textarea {
  resize: vertical;
}

.shell {
  min-height: 100vh;
}

.topbar {
  align-items: center;
  background: #ffffff;
  border-bottom: 1px solid #d9e0e8;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
}

.topbar h1 {
  font-size: 22px;
  line-height: 1;
  margin: 0;
}

.topbar p {
  color: #5f6d7a;
  margin: 4px 0 0;
}

.actions,
.mini-actions,
.queue-summary,
.next-cell {
  align-items: center;
  display: flex;
  gap: 8px;
}

.workspace {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  padding: 16px;
}

.sidebar,
.queue {
  min-width: 0;
}

.panel {
  background: #ffffff;
  border: 1px solid #d9e0e8;
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 14px;
}

.panel h2 {
  font-size: 14px;
  margin: 0 0 12px;
}

.panel label {
  color: #3f4d5a;
  display: block;
  font-size: 13px;
  margin-bottom: 10px;
}

.full {
  width: 100%;
}

.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  color: #9f1d15;
  margin: 12px 16px 0;
  padding: 10px 12px;
}

.queue {
  background: #ffffff;
  border: 1px solid #d9e0e8;
  border-radius: 8px;
  min-height: 560px;
  overflow: hidden;
}

.queue-summary {
  border-bottom: 1px solid #d9e0e8;
  justify-content: space-between;
  padding: 12px 14px;
}

.queue-summary span {
  color: #5f6d7a;
  margin-left: 12px;
}

.empty {
  color: #5f6d7a;
  padding: 32px 14px;
}

.table-wrap {
  overflow: auto;
}

table {
  border-collapse: collapse;
  min-width: 1040px;
  width: 100%;
}

th,
td {
  border-bottom: 1px solid #edf0f4;
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}

th {
  background: #f8fafc;
  color: #4a5967;
  font-size: 12px;
  font-weight: 700;
}

.paper-cell strong,
.paper-cell small,
.next-cell span {
  display: block;
}

.paper-cell strong {
  max-width: 320px;
  overflow-wrap: anywhere;
}

.paper-cell small {
  color: #687786;
  margin-top: 3px;
}

.badge {
  background: #eef4ff;
  border: 1px solid #c9dafc;
  border-radius: 999px;
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
}

.mini-actions {
  margin-top: 6px;
}

.mini-actions button {
  font-size: 12px;
  min-height: 26px;
  padding: 0 7px;
}

.next-cell {
  align-items: flex-start;
  flex-direction: column;
}

@media (max-width: 900px) {
  .topbar,
  .workspace {
    grid-template-columns: 1fr;
  }

  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
