<script setup>
import { openPath } from "@tauri-apps/plugin-opener";
import { computed, reactive, ref } from "vue";

const props = defineProps({
  batchFilter: { type: String, default: null },
  debugInfo: { type: Object, required: true },
  exportOptions: { type: Object, required: true },
  exportPreview: { type: Array, required: true },
  loading: Boolean,
  pipeline: { type: Array, required: true },
  selectedTaskIds: { type: Object, required: true },
  settings: { type: Object, required: true },
  tasks: { type: Array, required: true },
  workerStatus: { type: Object, required: true },
  zoteroStatus: { type: Object, required: true },
});
const emit = defineEmits([
  "attach-pdf",
  "clear-batch-filter",
  "cancel-export-preview",
  "confirm-export-selected",
  "generate-report",
  "generate-selected-reports",
  "open-home",
  "open-settings",
  "override-recommendation",
  "preview-export-selected",
  "probe-zotero",
  "process-all",
  "refresh",
  "remove-task",
  "remove-selected-tasks",
  "resolve-task",
  "retry-failed-tasks",
  "retry-task",
  "run-worker-once",
  "set-selection",
  "set-task-yolo",
  "set-worker-running",
  "skip-pdf",
  "toggle-selection",
]);

const activeTab = ref("current");
const inspectedTaskId = ref(null);
const showProgressDetails = ref(false);
const pendingBulkReport = ref(false);
const bulkReportType = ref(props.settings.default_report_type || "Quick Brief");
const rowChoices = reactive({});

const importedTasks = computed(() =>
  props.tasks.filter((task) => task.status === "Exported"),
);
const currentTasks = computed(() =>
  props.tasks.filter((task) => task.status !== "Exported"),
);
const activeBatch = computed(() => {
  if (!props.batchFilter) return null;
  const batchTasks = props.tasks.filter(
    (task) => (task.batch_id || task.task_id) === props.batchFilter,
  );
  if (!batchTasks.length) return null;
  return {
    id: props.batchFilter,
    label: batchTasks[0].batch_label || batchTasks[0].paper?.title || batchTasks[0].raw_input,
    count: batchTasks.length,
  };
});
const visibleTasks = computed(() =>
  (activeTab.value === "imported" ? importedTasks.value : currentTasks.value).filter(
    (task) => !props.batchFilter || (task.batch_id || task.task_id) === props.batchFilter,
  ),
);
const selectedCount = computed(() => props.selectedTaskIds.size);
const visibleTaskIds = computed(() => visibleTasks.value.map((task) => task.task_id));
const visibleSelectedCount = computed(
  () => visibleTaskIds.value.filter((taskId) => props.selectedTaskIds.has(taskId)).length,
);
const allVisibleSelected = computed(
  () => visibleTaskIds.value.length > 0 && visibleSelectedCount.value === visibleTaskIds.value.length,
);
const someVisibleSelected = computed(
  () => visibleSelectedCount.value > 0 && !allVisibleSelected.value,
);
const selectedTasks = computed(() =>
  props.tasks.filter((task) => props.selectedTaskIds.has(task.task_id)),
);
const inspectedTask = computed(() => {
  if (!inspectedTaskId.value) {
    return null;
  }
  return props.tasks.find((task) => task.task_id === inspectedTaskId.value) || null;
});
const reportTypes = computed(() => {
  const configured = Object.keys(props.settings.report_types || {});
  return configured.length ? configured : ["Quick Brief", "Standard Report", "Detailed Report"];
});
const retrySteps = computed(() => props.pipeline.filter((step) => step.key !== "zotero"));
const totalProgress = computed(() => {
  if (!props.tasks.length) {
    return { done: 0, total: 0, percent: 0 };
  }
  const done = props.tasks.filter((task) => task.status === "Exported").length;
  return {
    done,
    total: props.tasks.length,
    percent: Math.round((done / props.tasks.length) * 100),
  };
});
const totalCost = computed(() =>
  props.tasks.reduce((sum, task) => sum + (task.estimated_cost || 0), 0),
);
const failedCount = computed(() =>
  props.tasks.filter((task) => task.status === "Failed" || task.status.includes("failed")).length,
);
const reviewCount = computed(() =>
  props.tasks.filter((task) => task.status === "Needs disambiguation" || task.status === "Needs review").length,
);
const modelCallStatus = computed(() => {
  const active = props.tasks.find((task) =>
    ["Locating", "Evaluating", "Summarizing"].includes(task.status),
  );
  if (!active) return "空闲";
  return `${active.status}: ${active.paper?.title || active.raw_input}`;
});

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

/** Return whether the row can start report generation. */
function canGenerate(task) {
  return task.status === "Ready for report" || task.status === "Needs review";
}

/** Return generated report sections in display order. */
function reportSections(task) {
  return Object.entries(task?.report?.sections || {});
}

/** Return parsed PDF sections in display order. */
function parsedSections(task) {
  return Object.entries(task?.parsed?.sections || {});
}

/** Return candidate records for a disambiguation task. */
function candidates(task) {
  return task?.paper?.candidate_records || [];
}

/** Return compact text for task-level YOLO state. */
function yoloLabel(task) {
  if (task.yolo_enabled === true) return "YOLO on";
  if (task.yolo_enabled === false) return "YOLO off";
  return props.settings.yolo_default ? "YOLO default on" : "YOLO default off";
}

/** Convert task status into a visual progress percentage. */
function progressPercent(task) {
  const order = [
    "Queued",
    "Locating",
    "Located",
    "PDF ready",
    "Parsing",
    "Evaluating",
    "Ready for report",
    "Summarizing",
    "Ready for export",
    "Exported",
  ];
  if (task.status === "Budget paused") return 70;
  if (task.status === "Needs disambiguation" || task.status === "Needs review") return 35;
  if (task.status === "Failed" || task.status === "Parse failed") return 45;
  const index = Math.max(order.indexOf(task.status), 0);
  return Math.round((index / (order.length - 1)) * 100);
}

/** Return the recommended reading level shown in the list. */
function recommendation(task) {
  return task.evaluation?.value_recommendation || task.evaluation_status || "待评估";
}

/** Return the planned or generated report complexity. */
function reportComplexity(task) {
  return (
    task.report?.report_type ||
    task.evaluation?.suggested_report_type ||
    choices(task).reportType ||
    props.settings.default_report_type
  );
}

/** Return a Zotero-facing state string. */
function zoteroState(task) {
  if (task.status === "Exported") return "已导入";
  if (task.export_status && task.export_status !== "Not exported") return task.export_status;
  if (task.status === "Ready for export") return "待导出";
  return "未就绪";
}

/** Open the inspector for one task. */
function inspect(task) {
  inspectedTaskId.value = task.task_id;
}

/** Select or clear every task currently visible in the active list. */
function toggleVisibleSelection(checked) {
  const next = new Set(props.selectedTaskIds);
  for (const taskId of visibleTaskIds.value) {
    checked ? next.add(taskId) : next.delete(taskId);
  }
  emit("set-selection", [...next]);
}

/** Open the metadata editor for the inspected task. */
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

/** Convert the metadata editor draft into a PaperRecord-shaped payload. */
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

/** Render pipeline stages by combining backend step descriptors and task status fields. */
function pipelineRows(task) {
  const rows = [
    ["收集来源", task.input_type ? "已完成" : "等待中"],
    ["解析文件与链接", task.locator_status],
    ["匹配论文元数据", task.paper ? "已完成" : task.locator_status],
    ["去重与消歧", candidates(task).length ? "需复核" : task.paper ? "已完成" : "等待中"],
    ["获取 PDF", task.pdf_status],
    ["解析 PDF", task.parser_status],
    ["论文筛选与分类", task.evaluation?.value_recommendation || task.evaluation_status],
    ["生成阅读报告", task.report_status],
    ["写入 Zotero", zoteroState(task)],
  ];
  return rows.map(([label, status]) => ({ label, status: status || "等待中" }));
}

/** Choose status class for row icon and badges. */
function statusClass(task) {
  if (task.status === "Exported") return "ok";
  if (task.status === "Failed" || task.status === "Parse failed") return "bad";
  if (task.status.includes("Needs") || task.status === "Budget paused") return "warn";
  if (task.status.includes("ing")) return "active";
  return "idle";
}

/** Open a cached or user-provided PDF in the system viewer. */
async function openPdf(task) {
  if (task.pdf?.local_path) {
    await openPath(task.pdf.local_path);
  }
}

/** Open the PaperReady data directory that stores downloaded artifacts. */
async function openDataDir() {
  if (props.debugInfo.data_dir) {
    await openPath(props.debugInfo.data_dir);
  }
}

/** Generate reports after the in-app confirmation sheet is accepted. */
function confirmGenerateSelected() {
  pendingBulkReport.value = false;
  emit("generate-selected-reports", { reportType: bulkReportType.value });
}
</script>

<template>
  <section class="tasks-page" :class="{ 'no-inspector': !inspectedTask }">
    <div class="tasks-main">
      <header class="task-toolbar">
        <div class="segmented">
          <button
            type="button"
            :class="{ active: activeTab === 'current' }"
            @click="activeTab = 'current'"
          >
            当前任务
          </button>
          <button
            type="button"
            :class="{ active: activeTab === 'imported' }"
            @click="activeTab = 'imported'"
          >
            已导入
          </button>
        </div>
        <p class="queue-summary">
          {{ currentTasks.length }} 当前 · {{ importedTasks.length }} 已导入 · Worker
          {{ workerStatus.running ? "运行中" : "已停止" }}
        </p>
        <div class="toolbar-actions">
          <button type="button" :disabled="loading" title="刷新" @click="emit('refresh')">
            ↻
          </button>
          <button type="button" :disabled="loading" @click="emit('run-worker-once')">
            运行
          </button>
          <button type="button" :disabled="loading" @click="emit('process-all')">
            全部
          </button>
          <button
            type="button"
            :disabled="loading"
            @click="emit('set-worker-running', !workerStatus.running)"
          >
            {{ workerStatus.running ? "停止" : "启动" }}
          </button>
          <button
            type="button"
            :disabled="loading || failedCount === 0"
            @click="emit('retry-failed-tasks')"
          >
            重试失败
          </button>
          <button
            type="button"
            :disabled="loading || selectedCount === 0"
            @click="emit('remove-selected-tasks')"
          >
            移除
          </button>
        </div>
      </header>

      <section v-if="activeBatch" class="filter-strip">
        <span>筛选批次：{{ activeBatch.label }} · {{ activeBatch.count }} 篇</span>
        <button type="button" @click="emit('clear-batch-filter')">显示全部</button>
      </section>

      <section v-if="selectedCount > 0" class="bulk-bar">
        <strong>已选择 {{ selectedCount }} 篇文章</strong>
        <label>
          报告粒度
          <select v-model="bulkReportType">
            <option>不生成报告</option>
            <option v-for="type in reportTypes" :key="type">{{ type }}</option>
            <option>保留文章当前设置</option>
          </select>
        </label>
        <button
          type="button"
          :disabled="loading || bulkReportType === '不生成报告'"
          @click="pendingBulkReport = true"
        >
          生成报告
        </button>
        <button
          type="button"
          class="primary"
          :disabled="loading"
          @click="emit('preview-export-selected', exportOptions)"
        >
          导出到 Zotero
        </button>
      </section>

      <div v-if="visibleTasks.length === 0" class="empty-state">
        <strong>
          {{ activeTab === "current" ? "没有正在处理的文章" : "还没有导出到 Zotero 的文章" }}
        </strong>
        <span>
          {{ activeTab === "current" ? "从首页导入论文开始。" : "返回当前任务生成报告并导出。" }}
        </span>
        <div class="actions">
          <button
            v-if="activeTab === 'current'"
            type="button"
            class="primary"
            @click="emit('open-home')"
          >
            导入论文
          </button>
          <button
            v-if="activeTab === 'current'"
            type="button"
            @click="activeTab = 'imported'"
          >
            查看已导入
          </button>
          <button v-if="activeTab === 'imported'" type="button" @click="activeTab = 'current'">
            返回当前任务
          </button>
          <button
            v-if="activeTab === 'imported'"
            type="button"
            @click="emit('open-settings')"
          >
            打开 Zotero 设置
          </button>
        </div>
      </div>

      <div v-else class="article-list">
        <div class="article-head">
          <label class="select-all">
            <input
              type="checkbox"
              :checked="allVisibleSelected"
              :indeterminate="someVisibleSelected"
              @change="toggleVisibleSelection($event.target.checked)"
            />
            <span>文章</span>
          </label>
          <span>进度</span>
          <span>推荐阅读程度</span>
          <span>报告复杂度</span>
          <span>Zotero</span>
          <span>下一步</span>
        </div>
        <article
          v-for="task in visibleTasks"
          :key="task.task_id"
          class="article-row"
          :class="{ selected: inspectedTask?.task_id === task.task_id }"
          @click="inspect(task)"
        >
          <div class="article-title">
            <input
              type="checkbox"
              :checked="selectedTaskIds.has(task.task_id)"
              @click.stop
              @change="emit('toggle-selection', task.task_id)"
            />
            <span class="status-icon" :class="statusClass(task)"></span>
            <div>
              <strong>{{ task.paper?.title || task.raw_input }}</strong>
              <small>
                {{ task.paper?.venue || task.input_type }} · {{ task.paper?.year || "年份未知" }}
                · {{ yoloLabel(task) }}
              </small>
              <div class="line-progress">
                <span :style="{ width: `${progressPercent(task)}%` }"></span>
              </div>
            </div>
          </div>
          <div>
            <strong>{{ task.status }}</strong>
            <small>{{ progressPercent(task) }}%</small>
          </div>
          <div>
            <span class="badge">{{ recommendation(task) }}</span>
          </div>
          <div>{{ reportComplexity(task) }}</div>
          <div>{{ zoteroState(task) }}</div>
          <div class="row-actions">
            <span>{{ task.next_action }}</span>
            <button
              v-if="canGenerate(task)"
              type="button"
              @click.stop="emit('generate-report', task, choices(task))"
            >
              生成
            </button>
          </div>
        </article>
      </div>
    </div>

    <div
      v-if="exportPreview.length"
      class="export-preview-backdrop"
      @click.self="emit('cancel-export-preview')"
    >
      <section class="export-preview" role="dialog" aria-modal="true">
        <div class="export-preview-header">
          <div>
            <strong>Zotero 导出预览</strong>
            <span>
              {{ exportPreview.length }} 篇文章 · {{ settings.zotero_export_mode }} ·
              {{ zoteroStatus.available ? "Connector 可用" : "Connector 未连接" }}
            </span>
          </div>
          <button type="button" class="icon-button" title="关闭预览" @click="emit('cancel-export-preview')">
            ×
          </button>
        </div>
        <div class="export-preview-actions">
          <button type="button" @click="emit('probe-zotero')">检测 Zotero</button>
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
            报告 note
          </label>
          <label class="inline-field">
            导出模式
            <select
              :value="exportOptions.export_mode || settings.zotero_export_mode"
              @change="
                emit('preview-export-selected', {
                  ...exportOptions,
                  export_mode: $event.target.value,
                })
              "
            >
              <option value="prepare">仅准备 payload</option>
              <option value="connector">Zotero Connector</option>
              <option value="bridge">Bridge URL</option>
            </select>
          </label>
          <button type="button" @click="emit('cancel-export-preview')">取消</button>
          <button type="button" class="primary" @click="emit('confirm-export-selected')">
            确认导出
          </button>
        </div>
        <div class="preview-items">
          <article v-for="item in exportPreview" :key="item.task_id" class="preview-item">
            <strong>{{ item.title }}</strong>
            <span>
              {{ (item.creators || []).map((creator) => creator.name).join(", ") || "作者未知" }}
              · {{ item.date || "年份未知" }}
            </span>
            <span>{{ item.DOI || item.url || "无 DOI / URL" }}</span>
            <span>Tags: {{ (item.tags || []).join(", ") }}</span>
            <span>Collections: {{ (item.collections || []).join(", ") || "默认目标" }}</span>
            <small>
              {{ (item.attachments || []).length }} attachments ·
              {{ (item.notes || []).length }} notes · 可能重复项：未检测
            </small>
          </article>
        </div>
      </section>
    </div>

    <aside v-if="inspectedTask" class="task-inspector">
      <header>
        <div>
          <h3>{{ inspectedTask.paper?.title || inspectedTask.raw_input }}</h3>
          <p>{{ inspectedTask.status }} · {{ progressPercent(inspectedTask) }}%</p>
        </div>
        <button type="button" title="关闭详情" @click="inspectedTaskId = null">×</button>
      </header>

      <section class="inspector-section">
        <h4>概览</h4>
        <dl>
          <div><dt>推荐阅读程度</dt><dd>{{ recommendation(inspectedTask) }}</dd></div>
          <div><dt>报告复杂度</dt><dd>{{ reportComplexity(inspectedTask) }}</dd></div>
          <div><dt>YOLO</dt><dd>{{ yoloLabel(inspectedTask) }}</dd></div>
          <div><dt>PDF 状态</dt><dd>{{ inspectedTask.pdf_status }}</dd></div>
          <div><dt>Zotero 状态</dt><dd>{{ zoteroState(inspectedTask) }}</dd></div>
          <div><dt>Token / 成本</dt><dd>${{ (inspectedTask.estimated_cost || 0).toFixed(4) }}</dd></div>
        </dl>
        <div class="mini-actions yolo-actions">
          <button type="button" :disabled="loading" @click="emit('set-task-yolo', inspectedTask, true)">
            启用本文 YOLO
          </button>
          <button type="button" :disabled="loading" @click="emit('set-task-yolo', inspectedTask, false)">
            禁用本文 YOLO
          </button>
          <button type="button" :disabled="loading" @click="emit('set-task-yolo', inspectedTask, null)">
            跟随全局
          </button>
        </div>
      </section>

      <section class="inspector-section">
        <h4>Pipeline</h4>
        <div class="pipeline-list">
          <div v-for="row in pipelineRows(inspectedTask)" :key="row.label">
            <span>{{ row.label }}</span>
            <strong>{{ row.status }}</strong>
          </div>
        </div>
      </section>

      <section v-if="candidates(inspectedTask).length" class="inspector-section">
        <h4>消歧候选</h4>
        <article
          v-for="(candidate, index) in candidates(inspectedTask)"
          :key="`${inspectedTask.task_id}-${index}`"
          class="candidate-card"
        >
          <strong>{{ candidate.title }}</strong>
          <span>{{ candidate.venue || candidate.resolution_source }} · {{ candidate.year }}</span>
          <small>{{ candidate.doi || candidate.arxiv_id || candidate.urls?.[0] }}</small>
          <button type="button" @click="emit('resolve-task', inspectedTask, index)">
            选择
          </button>
        </article>
        <button type="button" @click="emit('remove-task', inspectedTask.task_id)">
          标记为非论文并移除
        </button>
      </section>

      <section class="inspector-section">
        <h4>元数据</h4>
        <button
          type="button"
          class="link-button"
          @click="startEditMetadata(inspectedTask)"
        >
          编辑元数据
        </button>
        <div v-if="choices(inspectedTask).editingMetadata" class="metadata-editor">
          <label>
            Title
            <input v-model="choices(inspectedTask).metadataDraft.title" type="text" />
          </label>
          <label>
            Authors
            <input v-model="choices(inspectedTask).metadataDraft.authors" type="text" />
          </label>
          <label>
            Year
            <input v-model="choices(inspectedTask).metadataDraft.year" type="number" />
          </label>
          <label>
            Venue
            <input v-model="choices(inspectedTask).metadataDraft.venue" type="text" />
          </label>
          <label>
            DOI
            <input v-model="choices(inspectedTask).metadataDraft.doi" type="text" />
          </label>
          <label>
            arXiv ID
            <input v-model="choices(inspectedTask).metadataDraft.arxiv_id" type="text" />
          </label>
          <label class="wide">
            URLs
            <textarea v-model="choices(inspectedTask).metadataDraft.urls" rows="2"></textarea>
          </label>
          <label class="wide">
            Abstract
            <textarea v-model="choices(inspectedTask).metadataDraft.abstract" rows="3"></textarea>
          </label>
          <div class="metadata-actions">
            <button type="button" class="primary" @click="saveMetadata(inspectedTask)">
              保存
            </button>
            <button type="button" @click="choices(inspectedTask).editingMetadata = false">
              取消
            </button>
          </div>
        </div>
      </section>

      <section class="inspector-section">
        <h4>下载数据</h4>
        <dl class="data-list">
          <div>
            <dt>缓存目录</dt>
            <dd>{{ debugInfo.data_dir || "未知" }}</dd>
          </div>
          <div>
            <dt>PDF 文件</dt>
            <dd>{{ inspectedTask.pdf?.local_path || "暂无本地缓存文件" }}</dd>
          </div>
          <div>
            <dt>来源 URL</dt>
            <dd>{{ inspectedTask.pdf?.source_url || inspectedTask.paper?.urls?.[0] || "暂无" }}</dd>
          </div>
          <div v-if="inspectedTask.pdf?.failure_reason || inspectedTask.failure_reason">
            <dt>失败原因</dt>
            <dd>{{ inspectedTask.pdf?.failure_reason || inspectedTask.failure_reason }}</dd>
          </div>
        </dl>
        <div class="mini-actions">
          <button type="button" :disabled="!debugInfo.data_dir" @click="openDataDir">
            打开 data 目录
          </button>
          <button
            type="button"
            :disabled="!inspectedTask.pdf?.local_path"
            @click="openPdf(inspectedTask)"
          >
            打开缓存 PDF
          </button>
          <button type="button" @click="emit('skip-pdf', inspectedTask)">
            跳过 PDF 继续
          </button>
          <button type="button" @click="emit('retry-task', inspectedTask, 'downloader')">
            重试 PDF 下载
          </button>
          <button type="button" @click="emit('retry-task', inspectedTask, 'parser')">
            重试解析
          </button>
        </div>
        <div class="pdf-controls">
          <input
            v-model="choices(inspectedTask).pdfPath"
            type="text"
            placeholder="Local PDF path"
          />
          <button
            type="button"
            :disabled="loading || !choices(inspectedTask).pdfPath"
            @click="emit('attach-pdf', inspectedTask, choices(inspectedTask).pdfPath)"
          >
            替换 PDF
          </button>
        </div>
      </section>

      <section class="inspector-section">
        <h4>PDF 解析结果</h4>
        <dl class="data-list">
          <div>
            <dt>解析状态</dt>
            <dd>{{ inspectedTask.parser_status }}</dd>
          </div>
          <div>
            <dt>解析质量</dt>
            <dd>{{ inspectedTask.parsed?.parse_quality || "暂无" }}</dd>
          </div>
          <div>
            <dt>Sections</dt>
            <dd>{{ parsedSections(inspectedTask).length }}</dd>
          </div>
          <div>
            <dt>References</dt>
            <dd>{{ inspectedTask.parsed?.references?.length || 0 }}</dd>
          </div>
        </dl>

        <div v-if="parsedSections(inspectedTask).length" class="parsed-preview">
          <details
            v-for="[heading, content] in parsedSections(inspectedTask)"
            :key="`${inspectedTask.task_id}-parsed-${heading}`"
          >
            <summary>{{ heading }}</summary>
            <pre>{{ content }}</pre>
          </details>
        </div>
        <p v-else>还没有可展示的 PDF 解析文本。可以重试解析，或在 metadata-only 状态下继续评估。</p>

        <details v-if="inspectedTask.parsed?.references?.length" class="parsed-references">
          <summary>References</summary>
          <ol>
            <li
              v-for="(reference, index) in inspectedTask.parsed.references"
              :key="`${inspectedTask.task_id}-ref-${index}`"
            >
              {{ reference }}
            </li>
          </ol>
        </details>
      </section>

      <section class="inspector-section">
        <h4>推荐判断</h4>
        <p>{{ inspectedTask.evaluation?.rationale || "还没有评估结果。" }}</p>
        <div class="mini-actions">
          <button type="button" @click="emit('override-recommendation', inspectedTask, 'Very Important')">
            Very Important
          </button>
          <button type="button" @click="emit('override-recommendation', inspectedTask, 'Brief Reading')">
            Brief Reading
          </button>
          <button type="button" @click="emit('override-recommendation', inspectedTask, 'Unrelated')">
            Unrelated
          </button>
        </div>
      </section>

      <section class="inspector-section">
        <h4>报告预览</h4>
        <div class="report-controls">
          <select v-model="choices(inspectedTask).reportType">
            <option v-for="type in reportTypes" :key="type">{{ type }}</option>
          </select>
          <input v-model="choices(inspectedTask).modelId" type="text" placeholder="Report model" />
          <button
            type="button"
            :disabled="loading || !canGenerate(inspectedTask)"
            @click="emit('generate-report', inspectedTask, choices(inspectedTask))"
          >
            生成报告
          </button>
        </div>
        <div v-if="reportSections(inspectedTask).length" class="report-preview">
          <section
            v-for="[heading, content] in reportSections(inspectedTask)"
            :key="`${inspectedTask.task_id}-${heading}`"
          >
            <strong>{{ heading }}</strong>
            <p>{{ content }}</p>
          </section>
        </div>
        <p v-else>报告尚未生成。</p>
      </section>

      <section v-if="inspectedTask.status === 'Budget paused'" class="inspector-section">
        <h4>预算暂停</h4>
        <p>
          预计成本 ${{ (inspectedTask.estimated_cost || 0).toFixed(4) }} · 当前批次预算
          ${{ settings.batch_budget }}
        </p>
        <div class="mini-actions">
          <button type="button" @click="choices(inspectedTask).reportType = 'Quick Brief'">
            降低报告复杂度
          </button>
          <button type="button" @click="emit('open-settings')">调整预算设置</button>
          <button
            type="button"
            @click="emit('generate-report', inspectedTask, choices(inspectedTask))"
          >
            仅对本文继续
          </button>
        </div>
      </section>

      <section class="inspector-section">
        <h4>Zotero 导出</h4>
        <p>
          {{ zoteroStatus.available ? "Zotero Connector 可用" : "Zotero Connector 未连接" }}
          · {{ settings.zotero_export_mode }}
        </p>
        <button
          type="button"
          class="primary"
          :disabled="loading"
          @click="
            emit('preview-export-selected', {
              ...exportOptions,
              task_ids: [inspectedTask.task_id],
            })
          "
        >
          预览并导出
        </button>
      </section>

      <section
        v-if="inspectedTask.failure_reason || inspectedTask.status === 'Failed'"
        class="inspector-section error-section"
      >
        <h4>错误与恢复</h4>
        <p>{{ inspectedTask.failure_reason || "处理失败，查看原始详情或重试。" }}</p>
        <details>
          <summary>原始错误详情</summary>
          <pre>{{ inspectedTask.failure_reason || inspectedTask }}</pre>
        </details>
        <div class="retry-controls">
          <select v-model="choices(inspectedTask).retryStep">
            <option v-for="step in retrySteps" :key="step.key" :value="step.key">
              {{ step.label }}
            </option>
          </select>
          <button
            type="button"
            :disabled="loading"
            @click="emit('retry-task', inspectedTask, choices(inspectedTask).retryStep)"
          >
            重试
          </button>
        </div>
      </section>
    </aside>

    <footer class="global-progress">
      <button type="button" @click="showProgressDetails = !showProgressDetails">
        正在处理 {{ currentTasks.length }} 篇论文 · {{ totalProgress.done }} /
        {{ totalProgress.total }} 已导入
      </button>
      <div class="global-progress-bar">
        <span :style="{ width: `${totalProgress.percent}%` }"></span>
      </div>
      <span>Token：${{ totalCost.toFixed(4) }} / ${{ settings.batch_budget }}</span>
      <button type="button" :disabled="loading" @click="emit('set-worker-running', false)">
        暂停全部
      </button>
      <div v-if="showProgressDetails" class="progress-popover">
        <strong>队列状态</strong>
        <span>运行中：{{ workerStatus.running ? "是" : "否" }}</span>
        <span>当前任务：{{ currentTasks.length }}</span>
        <span>失败：{{ failedCount }}</span>
        <span>需复核：{{ reviewCount }}</span>
        <span>当前模型调用状态：{{ modelCallStatus }}</span>
        <span>Worker 最近错误：{{ workerStatus.last_error || "无" }}</span>
      </div>
    </footer>

    <div v-if="pendingBulkReport" class="sheet-backdrop">
      <section class="sheet">
        <h3>更改 {{ selectedCount }} 篇文章的报告粒度？</h3>
        <p>
          已生成的报告不会自动重新生成，除非后续选择重新生成已完成报告。
        </p>
        <label class="checkbox-row">
          <input checked type="checkbox" />
          对后续未处理论文生效
        </label>
        <label class="checkbox-row">
          <input type="checkbox" />
          重新生成已完成报告
        </label>
        <label class="checkbox-row">
          <input checked type="checkbox" />
          保留原有人工修改内容
        </label>
        <div class="actions">
          <button type="button" @click="pendingBulkReport = false">取消</button>
          <button type="button" class="primary" @click="confirmGenerateSelected">
            应用
          </button>
        </div>
      </section>
    </div>
  </section>
</template>
