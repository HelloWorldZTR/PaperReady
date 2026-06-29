<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  backendReady: Boolean,
  loading: Boolean,
  tasks: { type: Array, required: true },
});
const emit = defineEmits(["create-tasks", "open-tasks"]);

const batchInput = ref("");
const isDragging = ref(false);
const fileQueue = ref([]);
const fileInput = ref(null);

const allowedExtensions = new Set(["pdf", "bib", "bibtex", "ris", "csv", "zip"]);

const inputLines = computed(() =>
  batchInput.value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean),
);
const duplicateLines = computed(() => {
  const seen = new Set();
  const duplicates = new Set();
  for (const line of inputLines.value) {
    const key = line.toLowerCase();
    if (seen.has(key)) {
      duplicates.add(line);
    }
    seen.add(key);
  }
  return [...duplicates];
});
const uncertainLines = computed(() =>
  inputLines.value.filter((line) => {
    const lower = line.toLowerCase();
    return (
      line.length < 8 ||
      (!lower.startsWith("http") &&
        !lower.includes("arxiv") &&
        !lower.includes("doi") &&
        !/\b10\.\d{4,9}\//.test(lower) &&
        !/\d{4}\.\d{4,5}/.test(lower))
    );
  }),
);
const blockingFiles = computed(() =>
  fileQueue.value.filter((file) => file.status === "不支持"),
);
const canSubmit = computed(
  () =>
    props.backendReady &&
    !props.loading &&
    inputLines.value.length > 0 &&
    blockingFiles.value.length === 0,
);
const recentBatches = computed(() => {
  const groups = new Map();
  for (const task of props.tasks) {
    const key = task.batch_id || task.task_id;
    const current = groups.get(key) || {
      id: key,
      label: task.batch_label || task.paper?.title || task.raw_input,
      count: 0,
      latest: task.updated_at || task.created_at,
      status: "已完成",
    };
    current.count += 1;
    if (new Date(task.updated_at || task.created_at) > new Date(current.latest)) {
      current.latest = task.updated_at || task.created_at;
    }
    if (task.status !== "Exported") {
      current.status = task.status.includes("Needs") ? "需复核" : "处理中";
    }
    groups.set(key, current);
  }
  return [...groups.values()]
    .sort((left, right) => new Date(right.latest) - new Date(left.latest))
    .slice(0, 5);
});

/** Submit recognized lines and queued file paths as article tasks. */
function submit() {
  if (!canSubmit.value) {
    return;
  }
  emit("create-tasks", inputLines.value.join("\n"));
}

/** Add a file path or display name into the text input once. */
function addInputLine(line) {
  const trimmed = line.trim();
  if (!trimmed) {
    return;
  }
  const existing = new Set(inputLines.value.map((item) => item.toLowerCase()));
  if (!existing.has(trimmed.toLowerCase())) {
    batchInput.value = [batchInput.value.trim(), trimmed].filter(Boolean).join("\n");
  }
}

/** Convert dropped files into the local file queue and batch input lines. */
function handleDrop(event) {
  isDragging.value = false;
  addFiles([...(event.dataTransfer?.files || [])]);
}

/** Add selected files into the queue. */
function handleFileSelection(event) {
  addFiles([...(event.target?.files || [])]);
  event.target.value = "";
}

/** Add file-like objects to the local file queue and batch input lines. */
function addFiles(files) {
  for (const file of files) {
    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    const supported = allowedExtensions.has(extension);
    const path = file.path || file.webkitRelativePath || file.name;
    fileQueue.value.push({
      id: `${file.name}-${file.size}-${file.lastModified}`,
      name: file.name,
      path,
      type: extension.toUpperCase() || "UNKNOWN",
      status: supported ? "等待解析" : "不支持",
    });
    if (supported) {
      addInputLine(path);
    }
  }
}

/** Return a compact icon label for the queued file type. */
function fileIcon(file) {
  if (file.type === "PDF") return "[PDF]";
  if (["BIB", "BIBTEX", "RIS", "CSV"].includes(file.type)) return "[TBL]";
  if (file.type === "ZIP") return "[ZIP]";
  return "[?]";
}

/** Format a task timestamp for the recent import list. */
function formatRecentTime(value) {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** Remove one queued file and its matching input line. */
function removeFile(file) {
  fileQueue.value = fileQueue.value.filter((item) => item.id !== file.id);
  batchInput.value = inputLines.value
    .filter((line) => line !== file.path)
    .join("\n");
}
</script>

<template>
  <section class="home-page">
    <div class="home-main">
      <header class="home-copy">
        <h1>导入论文</h1>
        <p>粘贴 DOI、标题、arXiv 链接，或拖入 PDF 开始。每行会创建一篇文章任务。</p>
      </header>

      <div v-if="!backendReady" class="inline-warning">
        Backend 未连接，正在尝试启动。你仍可以编辑输入，连接后再开始导入。
      </div>

      <div class="home-input">
        <textarea
          v-model="batchInput"
          placeholder="Paste DOI, arXiv ID, title, URL, or local file path. One item per line."
          rows="10"
          @keydown.meta.enter.prevent="submit"
          @keydown.ctrl.enter.prevent="submit"
        />
        <div class="input-hint">
          支持 DOI、arXiv、OpenReview、Semantic Scholar、出版社页面、PDF URL 和纯标题。
        </div>
        <button type="button" class="primary" :disabled="!canSubmit" @click="submit">
          ⇩ 开始导入
        </button>
      </div>

      <section class="preflight-panel">
        <strong>导入预检查</strong>
        <div class="preflight-grid">
          <span>已识别 {{ inputLines.length }} 条输入</span>
          <span>{{ duplicateLines.length }} 条疑似重复</span>
          <span>{{ uncertainLines.length }} 条会作为标题尝试匹配</span>
          <span>{{ blockingFiles.length }} 个文件不支持</span>
        </div>
        <ul v-if="duplicateLines.length || uncertainLines.length || blockingFiles.length">
          <li v-for="line in duplicateLines" :key="`dup-${line}`">疑似重复：{{ line }}</li>
          <li v-for="line in uncertainLines.slice(0, 3)" :key="`uncertain-${line}`">
            类型不确定，将进入任务中心复核：{{ line }}
          </li>
          <li v-for="file in blockingFiles" :key="`block-${file.id}`">
            不支持的文件：{{ file.name }}
          </li>
        </ul>
        <p v-if="blockingFiles.length" class="preflight-blocking">
          请先移除不支持的文件，再开始导入。
        </p>
      </section>
    </div>

    <aside class="home-side">
      <div
        class="drop-zone"
        :class="{ dragging: isDragging }"
        @dragenter.prevent="isDragging = true"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <div class="drop-icon">DOC</div>
        <strong>或导入本地文件</strong>
        <span>拖入 PDF、BibTeX、RIS、CSV 或 ZIP 文件，也可以从 Finder 选择文件。</span>
        <button type="button" @click="fileInput?.click()">选择文件...</button>
        <input
          ref="fileInput"
          accept=".pdf,.bib,.bibtex,.ris,.csv,.zip"
          class="visually-hidden"
          multiple
          type="file"
          @change="handleFileSelection"
        />
      </div>

      <div v-if="fileQueue.length" class="file-queue">
        <div class="file-row file-head">
          <span>文件</span>
          <span>类型</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        <div v-for="file in fileQueue" :key="file.id" class="file-row">
          <span>{{ fileIcon(file) }} {{ file.name }}</span>
          <span>{{ file.type }}</span>
          <span>{{ file.status }}</span>
          <button type="button" @click="removeFile(file)">移除</button>
        </div>
      </div>

      <section class="recent-imports">
        <header>
          <strong>最近导入</strong>
          <button type="button" class="link-button" @click="emit('open-tasks', null)">
            查看全部任务
          </button>
        </header>
        <div
          v-for="batch in recentBatches"
          :key="batch.id"
          class="recent-row"
          @click="emit('open-tasks', batch.id)"
        >
          <span>{{ formatRecentTime(batch.latest) }}</span>
          <span>{{ batch.label }}</span>
          <span>{{ batch.count }}</span>
          <span>{{ batch.status }}</span>
        </div>
        <p v-if="recentBatches.length === 0" class="recent-empty">
          还没有最近导入。
        </p>
      </section>
    </aside>
  </section>
</template>
