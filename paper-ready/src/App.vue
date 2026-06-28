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
          :selected-task-ids="selectedTaskIds"
          :tasks="tasks"
          @export-selected="exportSelected"
          @generate-report="generateReport"
          @override-recommendation="overrideRecommendation"
          @process-all="processAll"
          @refresh="refreshTasks"
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
