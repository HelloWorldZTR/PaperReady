<script setup>
import { invoke } from "@tauri-apps/api/core";
import { onMounted, ref } from "vue";
import { apiRequest, fallbackBackendUrl, resolveBackendUrl, waitForBackend } from "./api";
import HomePage from "./pages/HomePage.vue";
import SettingsPage from "./pages/SettingsPage.vue";
import TasksPage from "./pages/TasksPage.vue";
import { STRINGS } from "./strings";

const activePage = ref("home");
const taskBatchFilter = ref(null);
const backendUrl = ref(fallbackBackendUrl);
const tasks = ref([]);
const selectedTaskIds = ref(new Set());
const loading = ref(false);
const errorMessage = ref("");
const pipeline = ref([]);
const workerStatus = ref({ running: false, last_run_count: 0, last_error: null });
const zoteroStatus = ref({ available: false, connector_url: "", selected: null, error: null });
const exportPreview = ref([]);
const exportOptions = ref({
  include_pdf: true,
  include_notes: true,
  category: null,
  export_mode: null,
});
const backendReady = ref(false);
const debugInfo = ref({ db_path: "", data_dir: "", cache_size_bytes: 0, task_count: 0 });
const zoteroTestPayload = ref(null);
const promptDefaults = ref({});
const taskStats = ref({
  current_batch_cost: 0,
  daily_cost: 0,
  monthly_cost: 0,
  last_pause_reason: "",
});
const settings = ref({
  default_start_page: "home",
  research_interests: "",
  research_tags: [],
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
  zotero_default_collection: null,
  zotero_include_pdf_by_default: true,
  zotero_include_notes_by_default: true,
  zotero_collection_mapping: {},
  report_types: {},
  prompt_templates: {},
});

/** Call the local backend with the current resolved URL. */
async function api(path, options = {}) {
  return apiRequest(backendUrl.value, path, options);
}

/** Wait for the backend, retrying the managed Tauri process once if needed. */
async function ensureBackendReady() {
  try {
    await waitForBackend(backendUrl.value);
  } catch (firstError) {
    try {
      await invoke("restart_backend");
      await waitForBackend(backendUrl.value);
    } catch {
      throw firstError;
    }
  }
}

/** Load backend endpoint, settings, pipeline shape, and queue state. */
async function initialize() {
  loading.value = true;
  backendUrl.value = await resolveBackendUrl();
  try {
    await ensureBackendReady();
    settings.value = await api("/settings");
    try {
      promptDefaults.value = await api("/settings/prompt-defaults");
    } catch {
      promptDefaults.value = { ...(settings.value.prompt_templates || {}) };
    }
    activePage.value = settings.value.default_start_page || "home";
    exportOptions.value = {
      include_pdf: settings.value.zotero_include_pdf_by_default ?? true,
      include_notes: settings.value.zotero_include_notes_by_default ?? true,
      category: settings.value.zotero_default_collection || null,
      export_mode: settings.value.zotero_export_mode || null,
    };
    pipeline.value = await api("/pipeline");
    workerStatus.value = await api("/worker");
    await refreshDebugInfo();
    await probeZotero();
    await refreshTasks();
    backendReady.value = true;
  } catch (error) {
    backendReady.value = false;
    errorMessage.value = `Backend unavailable: ${error.message}`;
  } finally {
    loading.value = false;
  }
}

/** Refresh local storage diagnostics for Settings. */
async function refreshDebugInfo() {
  try {
    debugInfo.value = await api("/debug/storage");
  } catch {
    debugInfo.value = { db_path: "", data_dir: "", cache_size_bytes: 0, task_count: 0 };
  }
}

/** Clear PaperReady-owned cache files and refresh diagnostics. */
async function clearCache(mode) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api("/debug/cache/clear", {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    await refreshDebugInfo();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Restart the Tauri-managed backend process and reload diagnostics. */
async function restartBackend() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await invoke("restart_backend");
    await initialize();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Open the Tauri WebView developer tools. */
async function openDevtools() {
  try {
    await invoke("open_devtools");
  } catch (error) {
    errorMessage.value = error.message;
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

/** Build a safe sample Zotero payload for Settings diagnostics. */
async function sendZoteroTestPayload() {
  loading.value = true;
  errorMessage.value = "";
  try {
    zoteroTestPayload.value = await api("/zotero/test-payload", { method: "POST" });
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
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
  const totalCost = tasks.value.reduce((sum, task) => sum + (task.estimated_cost || 0), 0);
  taskStats.value = {
    current_batch_cost: totalCost,
    daily_cost: totalCost,
    monthly_cost: totalCost,
    last_pause_reason:
      tasks.value.find((task) => task.status === "Budget paused")?.failure_reason || "",
  };
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
    exportOptions.value = {
      include_pdf: settings.value.zotero_include_pdf_by_default ?? true,
      include_notes: settings.value.zotero_include_notes_by_default ?? true,
      category: settings.value.zotero_default_collection || null,
      export_mode: settings.value.zotero_export_mode || null,
    };
    await refreshDebugInfo();
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
    const inputs = rawInput
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (inputs.length === 0) {
      return;
    }
    await api("/tasks", {
      method: "POST",
      body: JSON.stringify({ inputs }),
    });
    await refreshTasks();
    taskBatchFilter.value = null;
    activePage.value = "tasks";
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Remove one or more selected articles from the local task queue. */
async function removeSelectedTasks() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await Promise.all(
      [...selectedTaskIds.value].map((taskId) =>
        api(`/tasks/${taskId}`, { method: "DELETE" }),
      ),
    );
    selectedTaskIds.value = new Set();
    exportPreview.value = [];
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Remove a single article from the local task queue. */
async function removeTask(taskId) {
  const previous = selectedTaskIds.value;
  selectedTaskIds.value = new Set([taskId]);
  await removeSelectedTasks();
  if (selectedTaskIds.value.size !== 0) {
    selectedTaskIds.value = previous;
  }
}

/** Generate reports for all selected rows that can be summarized. */
async function generateSelectedReports(options = {}) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const selectedTasks = tasks.value.filter((task) => selectedTaskIds.value.has(task.task_id));
    await Promise.all(
      selectedTasks
        .filter((task) => task.status === "Ready for report" || task.status === "Needs review")
        .map((task) =>
          api(`/tasks/${task.task_id}/report`, {
            method: "POST",
            body: JSON.stringify({
              report_type:
                options.reportType ||
                task.evaluation?.suggested_report_type ||
                settings.value.default_report_type,
              model_id: options.modelId || settings.value.summarization_model,
            }),
          }),
        ),
    );
    await refreshTasks();
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

/** Retry failed selected rows, or all failed rows when nothing is selected. */
async function retryFailedTasks() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const selected = tasks.value.filter((task) => selectedTaskIds.value.has(task.task_id));
    const scope = selected.length ? selected : tasks.value;
    const failed = scope.filter(
      (task) =>
        task.status === "Failed" ||
        task.status === "Parse failed" ||
        task.status === "Budget paused" ||
        task.failure_reason,
    );
    await Promise.all(
      failed.map((task) =>
        api(`/tasks/${task.task_id}/retry`, {
          method: "POST",
          body: JSON.stringify({ step: null }),
        }),
      ),
    );
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Attach or replace a task's local PDF path. */
async function attachPdf(task, path) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api(`/tasks/${task.task_id}/pdf`, {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Continue a task without PDF parsing by switching it to metadata-only. */
async function skipPdf(task) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api(`/tasks/${task.task_id}/skip-pdf`, { method: "POST" });
    await refreshTasks();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    loading.value = false;
  }
}

/** Set task-level YOLO override for all selected rows. */
async function setSelectedYolo(enabled) {
  loading.value = true;
  errorMessage.value = "";
  try {
    await Promise.all(
      [...selectedTaskIds.value].map((taskId) =>
        api(`/tasks/${taskId}/yolo`, {
          method: "POST",
          body: JSON.stringify({ enabled }),
        }),
      ),
    );
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

/** Open the task center, optionally filtered to one import batch. */
function openTasks(batchId = null) {
  taskBatchFilter.value = batchId;
  activePage.value = "tasks";
}

onMounted(initialize);
</script>

<template>
  <main class="app-shell">
    <header class="titlebar" data-tauri-drag-region>
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
        <div class="sidebar-main">
          <button
            v-for="(label, key) in STRINGS.nav"
            :key="key"
            type="button"
            :class="{ active: activePage === key }"
            @click="activePage = key"
          >
            {{ label }}
          </button>
        </div>
        <footer class="sidebar-status">
          <div>
            <span class="status-dot" :class="backendReady ? 'ok' : 'bad'"></span>
            Backend {{ backendReady ? "运行中" : "未连接" }}
          </div>
          <div>
            <span class="status-dot" :class="zoteroStatus.available ? 'ok' : 'warn'"></span>
            Zotero {{ zoteroStatus.available ? "已连接" : "未检测" }}
          </div>
          <div>
            <span class="status-dot" :class="workerStatus.running ? 'ok' : 'idle'"></span>
            Worker {{ workerStatus.running ? "运行中" : "已停止" }}
          </div>
          <label class="sidebar-yolo">
            <input
              :checked="settings.yolo_default"
              type="checkbox"
              @change="settings = { ...settings, yolo_default: $event.target.checked }"
            />
            YOLO 模式
          </label>
        </footer>
      </nav>

      <section class="page-host" :class="{ flush: activePage !== 'home' }">
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        <HomePage
          v-if="activePage === 'home'"
          :backend-ready="backendReady"
          :loading="loading"
          :tasks="tasks"
          @create-tasks="createTasks"
          @open-tasks="openTasks"
        />
        <TasksPage
          v-else-if="activePage === 'tasks'"
          :batch-filter="taskBatchFilter"
          :loading="loading"
          :pipeline="pipeline"
          :settings="settings"
          :selected-task-ids="selectedTaskIds"
          :tasks="tasks"
          :worker-status="workerStatus"
          :zotero-status="zoteroStatus"
          :export-preview="exportPreview"
          :export-options="exportOptions"
          @attach-pdf="attachPdf"
          @cancel-export-preview="cancelExportPreview"
          @confirm-export-selected="confirmExportSelected"
          @preview-export-selected="previewExportSelected"
          @probe-zotero="probeZotero"
          @generate-report="generateReport"
          @generate-selected-reports="generateSelectedReports"
          @open-home="activePage = 'home'"
          @open-settings="activePage = 'settings'"
          @clear-batch-filter="taskBatchFilter = null"
          @override-recommendation="overrideRecommendation"
          @process-all="processAll"
          @refresh="refreshTasks"
          @resolve-task="resolveTask"
          @retry-task="retryTask"
          @retry-failed-tasks="retryFailedTasks"
          @remove-selected-tasks="removeSelectedTasks"
          @remove-task="removeTask"
          @run-worker-once="runWorkerOnce"
          @set-selected-yolo="setSelectedYolo"
          @set-worker-running="setWorkerRunning"
          @skip-pdf="skipPdf"
          @toggle-selection="toggleSelection"
        />
        <SettingsPage
          v-else
          :backend-url="backendUrl"
          :debug-info="debugInfo"
          :loading="loading"
          :prompt-defaults="promptDefaults"
          :settings="settings"
          :task-stats="taskStats"
          :worker-status="workerStatus"
          :zotero-status="zoteroStatus"
          :zotero-test-payload="zoteroTestPayload"
          @clear-cache="clearCache"
          @open-devtools="openDevtools"
          @probe-zotero="probeZotero"
          @restart-backend="restartBackend"
          @send-zotero-test-payload="sendZoteroTestPayload"
          @save-settings="saveSettings"
          @update:settings="settings = $event"
        />
      </section>
    </section>
  </main>
</template>
