<script setup>
import { getCurrentWindow } from "@tauri-apps/api/window";
import { onMounted, ref } from "vue";
import { apiRequest, fallbackBackendUrl, resolveBackendUrl } from "./api";
import HomePage from "./pages/HomePage.vue";
import SettingsPage from "./pages/SettingsPage.vue";
import TasksPage from "./pages/TasksPage.vue";
import { STRINGS } from "./strings";

const appWindow = getCurrentWindow();
const activePage = ref("home");
const backendUrl = ref(fallbackBackendUrl);
const tasks = ref([]);
const selectedTaskIds = ref(new Set());
const loading = ref(false);
const errorMessage = ref("");
const pipeline = ref([]);
const workerStatus = ref({ running: false, last_run_count: 0, last_error: null });
const zoteroStatus = ref({ available: false, connector_url: "", selected: null, error: null });
const exportPreview = ref([]);
const exportOptions = ref({ include_pdf: true, include_notes: true, category: null });
const settings = ref({
  research_interests: "",
  batch_budget: 3,
  llm_api_base_url: "https://api.openai.com/v1",
  locating_model: "gpt-4.1-mini",
  evaluation_model: "gpt-4.1-mini",
  summarization_model: "gpt-4.1",
  locating_concurrency: 2,
  evaluation_concurrency: 2,
  summarization_concurrency: 1,
  default_report_type: "Quick Brief",
  daily_budget: null,
  monthly_budget: null,
  yolo_default: false,
  budget_overflow_behavior: "pause",
  language_preference: "en",
  zotero_bridge_url: null,
  zotero_connector_url: "http://127.0.0.1:23119",
  zotero_export_mode: "prepare",
  report_types: {},
  prompt_templates: {},
});

/** Call the local backend with the current resolved URL. */
async function api(path, options = {}) {
  return apiRequest(backendUrl.value, path, options);
}

/** Load backend endpoint, settings, pipeline shape, and queue state. */
async function initialize() {
  loading.value = true;
  backendUrl.value = await resolveBackendUrl();
  try {
    settings.value = await api("/settings");
    pipeline.value = await api("/pipeline");
    workerStatus.value = await api("/worker");
    await probeZotero();
    await refreshTasks();
  } catch (error) {
    errorMessage.value = `Backend unavailable: ${error.message}`;
  } finally {
    loading.value = false;
  }
}

/** Probe Zotero Connector readiness without writing to the library. */
async function probeZotero() {
  try {
    zoteroStatus.value = await api("/zotero/status");
  } catch (error) {
    zoteroStatus.value = {
      available: false,
      connector_url: settings.value.zotero_connector_url || "",
      selected: null,
      error: error.message,
    };
  }
}

/** Run one background-worker pass and refresh visible queue state. */
async function runWorkerOnce() {
  loading.value = true;
  errorMessage.value = "";
  try {
    workerStatus.value = await api("/worker/run-once", { method: "POST" });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Start or stop the background queue worker. */
async function setWorkerRunning(shouldRun) {
  loading.value = true;
  errorMessage.value = "";
  try {
    workerStatus.value = await api(shouldRun ? "/worker/start" : "/worker/stop", {
      method: "POST",
    });
  } catch (error) {
    errorMessage.value = error.message;
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
  errorMessage.value = "";
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

/** Create queue tasks from the Home page input and switch to Tasks. */
async function createTasks(rawInput) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const inputs = rawInput.split("\n").map((line) => line.trim());
    await api("/tasks", {
      method: "POST",
      body: JSON.stringify({ inputs }),
    });
    await refreshTasks();
    activePage.value = "tasks";
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Advance every safe task through the backend pipeline. */
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
async function generateReport(task, selection = {}) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api(`/tasks/${task.task_id}/report`, {
      method: "POST",
      body: JSON.stringify({
        report_type:
          selection.reportType ||
          task.evaluation?.suggested_report_type ||
          settings.value.default_report_type,
        model_id: selection.modelId || settings.value.summarization_model,
      }),
    });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Reset a task from a selected pipeline stage and run automatic processing. */
async function retryTask(task, step) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api(`/tasks/${task.task_id}/retry`, {
      method: "POST",
      body: JSON.stringify({ step }),
    });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Resolve a task with a candidate selection or user-edited metadata. */
async function resolveTask(task, resolution) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const body =
      typeof resolution === "number"
        ? { candidate_index: resolution }
        : { paper: resolution };
    await api(`/tasks/${task.task_id}/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
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
  errorMessage.value = "";
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

/** Build a Zotero export preview before the user confirms save. */
async function previewExportSelected(options = exportOptions.value) {
  loading.value = true;
  errorMessage.value = "";
  try {
    exportOptions.value = { ...exportOptions.value, ...options };
    exportPreview.value = await api("/export/zotero/preview", {
      method: "POST",
      body: JSON.stringify({
        task_ids: [...selectedTaskIds.value],
        ...exportOptions.value,
      }),
    });
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Confirm Zotero export intent for selected rows. */
async function confirmExportSelected() {
  loading.value = true;
  errorMessage.value = "";
  try {
    tasks.value = await api("/export/zotero", {
      method: "POST",
      body: JSON.stringify({
        task_ids: [...selectedTaskIds.value],
        ...exportOptions.value,
      }),
    });
    selectedTaskIds.value = new Set();
    exportPreview.value = [];
    await probeZotero();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Clear the pending Zotero preview. */
function cancelExportPreview() {
  exportPreview.value = [];
}

/** Toggle a task row in the export selection. */
function toggleSelection(taskId) {
  const next = new Set(selectedTaskIds.value);
  next.has(taskId) ? next.delete(taskId) : next.add(taskId);
  selectedTaskIds.value = next;
}

/** Ask the native window to minimize from the custom title bar. */
function minimizeWindow() {
  appWindow.minimize();
}

/** Ask the native window to close from the custom title bar. */
function closeWindow() {
  appWindow.close();
}

onMounted(initialize);
</script>

<template>
  <main class="app-shell">
    <header class="titlebar" data-tauri-drag-region>
      <div class="traffic-lights">
        <button class="traffic close" aria-label="Close" @click="closeWindow"></button>
        <button class="traffic minimize" aria-label="Minimize" @click="minimizeWindow"></button>
        <button class="traffic zoom" aria-label="Zoom" disabled></button>
      </div>
      <div class="titlebar-title" data-tauri-drag-region>
        <strong>{{ STRINGS.appName }}</strong>
        <span>{{ STRINGS.subtitle }}</span>
      </div>
      <div class="pipeline-pills">
        <span v-for="step in pipeline" :key="step.key">{{ step.label }}</span>
      </div>
    </header>

    <section class="content-shell">
      <nav class="sidebar-nav">
        <button
          v-for="(label, key) in STRINGS.nav"
          :key="key"
          type="button"
          :class="{ active: activePage === key }"
          @click="activePage = key"
        >
          {{ label }}
        </button>
      </nav>

      <section class="page-host">
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        <HomePage
          v-if="activePage === 'home'"
          :loading="loading"
          @create-tasks="createTasks"
        />
        <TasksPage
          v-else-if="activePage === 'tasks'"
          :loading="loading"
          :pipeline="pipeline"
          :settings="settings"
          :selected-task-ids="selectedTaskIds"
          :tasks="tasks"
          :worker-status="workerStatus"
          :zotero-status="zoteroStatus"
          :export-preview="exportPreview"
          :export-options="exportOptions"
          @cancel-export-preview="cancelExportPreview"
          @confirm-export-selected="confirmExportSelected"
          @preview-export-selected="previewExportSelected"
          @probe-zotero="probeZotero"
          @generate-report="generateReport"
          @override-recommendation="overrideRecommendation"
          @process-all="processAll"
          @refresh="refreshTasks"
          @resolve-task="resolveTask"
          @retry-task="retryTask"
          @run-worker-once="runWorkerOnce"
          @set-worker-running="setWorkerRunning"
          @toggle-selection="toggleSelection"
        />
        <SettingsPage
          v-else
          :loading="loading"
          :settings="settings"
          @save-settings="saveSettings"
          @update:settings="settings = $event"
        />
      </section>
    </section>
  </main>
</template>
