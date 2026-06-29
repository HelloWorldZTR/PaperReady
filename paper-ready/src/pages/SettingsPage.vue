<script setup>
import { openPath, openUrl } from "@tauri-apps/plugin-opener";
import { computed, ref } from "vue";

const props = defineProps({
  backendUrl: { type: String, required: true },
  debugInfo: { type: Object, required: true },
  loading: Boolean,
  promptDefaults: { type: Object, required: true },
  settings: { type: Object, required: true },
  taskStats: { type: Object, required: true },
  workerStatus: { type: Object, required: true },
  zoteroStatus: { type: Object, required: true },
  zoteroTestPayload: { type: Object, default: null },
});
const emit = defineEmits([
  "clear-cache",
  "open-devtools",
  "probe-zotero",
  "restart-backend",
  "save-settings",
  "send-zotero-test-payload",
  "update:settings",
]);

const activeSection = ref("general");
const visibleApiKey = ref(false);
const selectedPrompt = ref("Evaluator prompt");
const tagDraft = ref("");
const promptDirty = ref(false);
const appVersion = __APP_VERSION__;
const buildId = __BUILD_ID__;
const pendingClearAll = ref(false);

const sections = [
  ["general", "通用"],
  ["interests", "研究兴趣"],
  ["models", "模型与 Token"],
  ["prompts", "Prompts"],
  ["zotero", "Zotero 与导出"],
  ["privacy", "隐私与缓存"],
  ["diagnostics", "诊断"],
];

const promptVariables = [
  "{{title}}",
  "{{abstract}}",
  "{{authors}}",
  "{{venue}}",
  "{{year}}",
  "{{doi}}",
  "{{arxiv_id}}",
  "{{pdf_text}}",
  "{{sections}}",
  "{{references}}",
  "{{user_research_context}}",
  "{{value_recommendation}}",
];
const promptPreviewValues = computed(() => ({
  "{{title}}": "Diffusion Policy for Robot Manipulation",
  "{{abstract}}": "Example abstract preview...",
  "{{authors}}": "Jane Doe, Alan Smith",
  "{{venue}}": "ICRA",
  "{{year}}": "2026",
  "{{doi}}": "10.0000/example",
  "{{arxiv_id}}": "2601.00001",
  "{{pdf_text}}": "Example parsed PDF text...",
  "{{sections}}": '{"abstract": "Example abstract", "method": "Example method"}',
  "{{references}}": '["Reference 1", "Reference 2"]',
  "{{user_research_context}}": props.settings.research_interests || "User research interests",
  "{{value_recommendation}}": "Brief Reading",
}));

const promptKeys = computed(() => {
  const keys = [
    ...new Set([
      ...Object.keys(props.promptDefaults || {}),
      ...Object.keys(props.settings.prompt_templates || {}),
    ]),
  ];
  return keys.length
    ? keys
    : [
        "Locator prompt",
        "Evaluator prompt",
        "Quick Brief prompt",
        "Standard Report prompt",
        "Detailed Report prompt",
        "Zotero note prompt",
      ];
});
const cacheSize = computed(() => {
  const bytes = props.debugInfo.cache_size_bytes || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
});
const promptDraft = computed(
  () =>
    props.settings.prompt_templates?.[selectedPrompt.value] ||
    props.promptDefaults?.[selectedPrompt.value] ||
    "",
);
const finalPromptPreview = computed(() =>
  Object.entries(promptPreviewValues.value).reduce(
    (preview, [variable, value]) => preview.replaceAll(variable, value),
    promptDraft.value,
  ),
);
const promptError = computed(() => {
  if (!promptDraft.value.trim()) {
    return "Prompt 不能为空。";
  }
  const opens = (promptDraft.value.match(/\{\{/g) || []).length;
  const closes = (promptDraft.value.match(/\}\}/g) || []).length;
  return opens === closes ? "" : "Prompt 变量括号未闭合。";
});

/** Update one field in the settings model owned by App.vue. */
function updateField(key, value) {
  emit("update:settings", { ...props.settings, [key]: value });
}

/** Update the selected prompt template. */
function updatePrompt(value) {
  promptDirty.value = true;
  emit("update:settings", {
    ...props.settings,
    prompt_templates: {
      ...(props.settings.prompt_templates || {}),
      [selectedPrompt.value]: value,
    },
  });
}

/** Add one structured research tag used by evaluator and summarizer context. */
function addResearchTag() {
  const tag = tagDraft.value.trim();
  if (!tag) return;
  const tags = new Set(props.settings.research_tags || []);
  tags.add(tag);
  updateField("research_tags", [...tags]);
  tagDraft.value = "";
}

/** Remove one structured research tag. */
function removeResearchTag(tag) {
  updateField(
    "research_tags",
    (props.settings.research_tags || []).filter((item) => item !== tag),
  );
}

/** Update one Zotero recommendation-to-collection mapping entry. */
function updateCollectionMapping(key, value) {
  updateField("zotero_collection_mapping", {
    ...(props.settings.zotero_collection_mapping || {}),
    [key]: value,
  });
}

/** Insert a variable token into the current prompt template. */
function insertVariable(variable) {
  updatePrompt(`${promptDraft.value}\n${variable}`);
}

/** Reset the selected prompt to the backend-owned default template. */
function restorePromptDefault() {
  const defaultPrompt = props.promptDefaults?.[selectedPrompt.value];
  if (defaultPrompt) {
    updatePrompt(defaultPrompt);
  }
}

/** Format a settings object as editable JSON. */
function formatJson(value) {
  return JSON.stringify(value || {}, null, 2);
}

/** Parse editable JSON and update a settings object field when valid. */
function updateJsonField(key, value) {
  try {
    updateField(key, JSON.parse(value || "{}"));
  } catch {
    // Keep the user's draft visible until it becomes valid JSON.
  }
}

/** Open the local PaperReady data directory with the OS file manager. */
async function openDataDir() {
  if (props.debugInfo.data_dir) {
    await openPath(props.debugInfo.data_dir);
  }
}

/** Ask the OS to open Zotero through its URL scheme. */
async function openZotero() {
  await openUrl("zotero://select");
}

/** Download a compact diagnostics JSON file from the current UI state. */
function exportDiagnostics() {
  const payload = {
    backendUrl: props.backendUrl,
    debugInfo: props.debugInfo,
    workerStatus: props.workerStatus,
    zoteroStatus: props.zoteroStatus,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "paperready-diagnostics.json";
  link.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <section class="settings-shell">
    <nav class="settings-sidebar">
      <button
        v-for="[key, label] in sections"
        :key="key"
        type="button"
        :class="{ active: activeSection === key }"
        @click="activeSection = key"
      >
        {{ label }}
      </button>
    </nav>

    <main class="settings-content">
      <header class="page-header">
        <div>
          <h2>设置</h2>
          <p>模型、预算、Prompt、Zotero 和本地运行配置。</p>
        </div>
        <button type="button" class="primary" :disabled="loading" @click="emit('save-settings')">
          保存设置
        </button>
      </header>

      <section v-if="activeSection === 'general'" class="settings-form">
        <label>
          默认启动页面
          <select
            :value="settings.default_start_page"
            @change="updateField('default_start_page', $event.target.value)"
          >
            <option value="home">导入</option>
            <option value="tasks">任务</option>
          </select>
        </label>
        <label>
          默认报告类型
          <select
            :value="settings.default_report_type"
            @change="updateField('default_report_type', $event.target.value)"
          >
            <option>Quick Brief</option>
            <option>Standard Report</option>
            <option>Detailed Report</option>
          </select>
        </label>
        <label>
          预算超限行为
          <select
            :value="settings.budget_overflow_behavior"
            @change="updateField('budget_overflow_behavior', $event.target.value)"
          >
            <option value="pause">暂停并询问</option>
            <option value="deny">禁止继续</option>
            <option value="allow_once">允许本批次继续</option>
          </select>
        </label>
        <label>
          语言偏好
          <select
            :value="settings.language_preference"
            @change="updateField('language_preference', $event.target.value)"
          >
            <option value="system">跟随系统</option>
            <option value="en">English</option>
            <option value="zh">简体中文</option>
          </select>
        </label>
        <label class="checkbox-row wide">
          <input
            :checked="settings.yolo_default"
            type="checkbox"
            @change="updateField('yolo_default', $event.target.checked)"
          />
          YOLO 默认开启
        </label>
        <p class="settings-note">
          YOLO 会让后台 Worker 对符合条件的文章自动生成报告，但仍会遵守预算限制，且 Zotero 导出始终需要用户确认。
        </p>
      </section>

      <section v-else-if="activeSection === 'interests'" class="settings-form">
        <label class="wide">
          研究兴趣
          <textarea
            :value="settings.research_interests"
            placeholder="我关注机器人操作、具身智能、视觉语言动作模型、长程任务规划和可复现实验。"
            rows="10"
            @input="updateField('research_interests', $event.target.value)"
          />
        </label>
        <div class="wide tag-editor">
          <label>
            结构化标签
            <div class="api-key-row">
              <input
                v-model="tagDraft"
                placeholder="例如 VLA, robotic manipulation, reproducibility"
                type="text"
                @keydown.enter.prevent="addResearchTag"
              />
              <button type="button" @click="addResearchTag">添加</button>
            </div>
          </label>
          <div v-if="settings.research_tags?.length" class="tag-list">
            <button
              v-for="tag in settings.research_tags"
              :key="tag"
              type="button"
              @click="removeResearchTag(tag)"
            >
              {{ tag }} ×
            </button>
          </div>
        </div>
        <p class="settings-note">
          此内容会被用于推荐阅读程度和报告生成，不会自动写入 Zotero。
        </p>
      </section>

      <section v-else-if="activeSection === 'models'" class="settings-form">
        <label>
          API Base URL
          <input
            :value="settings.llm_api_base_url"
            type="text"
            @input="updateField('llm_api_base_url', $event.target.value)"
          />
        </label>
        <label>
          API Key
          <div class="api-key-row">
            <input
              :value="settings.api_key"
              :type="visibleApiKey ? 'text' : 'password'"
              autocomplete="off"
              placeholder="Stored locally for configured provider"
              @input="updateField('api_key', $event.target.value)"
            />
            <button type="button" @click="visibleApiKey = !visibleApiKey">
              {{ visibleApiKey ? "隐藏" : "显示" }}
            </button>
          </div>
        </label>
        <label>
          定位模型
          <input
            :value="settings.locating_model"
            type="text"
            @input="updateField('locating_model', $event.target.value)"
          />
        </label>
        <label>
          评估模型
          <input
            :value="settings.evaluation_model"
            type="text"
            @input="updateField('evaluation_model', $event.target.value)"
          />
        </label>
        <label>
          总结模型
          <input
            :value="settings.summarization_model"
            type="text"
            @input="updateField('summarization_model', $event.target.value)"
          />
        </label>
        <label>
          每批预算
          <input
            :value="settings.batch_budget"
            min="0"
            step="0.01"
            type="number"
            @input="updateField('batch_budget', Number($event.target.value))"
          />
        </label>
        <label>
          每日预算
          <input
            :value="settings.daily_budget"
            min="0"
            step="0.01"
            type="number"
            @input="updateField('daily_budget', Number($event.target.value) || null)"
          />
        </label>
        <label>
          每月预算
          <input
            :value="settings.monthly_budget"
            min="0"
            step="0.01"
            type="number"
            @input="updateField('monthly_budget', Number($event.target.value) || null)"
          />
        </label>
        <label>
          定位并发
          <input
            :value="settings.locating_concurrency"
            min="1"
            type="number"
            @input="updateField('locating_concurrency', Number($event.target.value))"
          />
        </label>
        <label>
          评估并发
          <input
            :value="settings.evaluation_concurrency"
            min="1"
            type="number"
            @input="updateField('evaluation_concurrency', Number($event.target.value))"
          />
        </label>
        <label>
          总结并发
          <input
            :value="settings.summarization_concurrency"
            min="1"
            type="number"
            @input="updateField('summarization_concurrency', Number($event.target.value))"
          />
        </label>
        <dl class="diagnostic-list wide">
          <div><dt>当前批次已用</dt><dd>${{ taskStats.current_batch_cost.toFixed(4) }}</dd></div>
          <div><dt>今日已用</dt><dd>${{ taskStats.daily_cost.toFixed(4) }}</dd></div>
          <div><dt>本月已用</dt><dd>${{ taskStats.monthly_cost.toFixed(4) }}</dd></div>
          <div><dt>最近一次暂停原因</dt><dd>{{ taskStats.last_pause_reason || "无" }}</dd></div>
        </dl>
        <p class="settings-note">
          当前 API Key 随设置保存在本地 SQLite 设置记录中；后续接入平台安全存储时可迁移，诊断页会显示数据库位置。
        </p>
      </section>

      <section v-else-if="activeSection === 'prompts'" class="settings-form">
        <label>
          Prompt 类型
          <select v-model="selectedPrompt">
            <option v-for="key in promptKeys" :key="key">{{ key }}</option>
          </select>
        </label>
        <div class="wide variable-row">
          <button
            v-for="variable in promptVariables"
            :key="variable"
            type="button"
            @click="insertVariable(variable)"
          >
            {{ variable }}
          </button>
        </div>
        <label class="wide">
          Prompt 编辑器
          <textarea
            :value="promptDraft"
            rows="12"
            @input="updatePrompt($event.target.value)"
          />
        </label>
        <p v-if="promptDirty || promptError" class="settings-note" :class="{ invalid: promptError }">
          {{ promptError || "Prompt 有未保存修改。" }}
        </p>
        <div class="wide actions">
          <button type="button" @click="restorePromptDefault">恢复默认</button>
        </div>
        <label class="wide">
          最终 Prompt 预览
          <textarea :value="finalPromptPreview" readonly rows="8"></textarea>
        </label>
        <label class="wide">
          Report types JSON
          <textarea
            :value="formatJson(settings.report_types)"
            rows="8"
            @change="updateJsonField('report_types', $event.target.value)"
          />
        </label>
      </section>

      <section v-else-if="activeSection === 'zotero'" class="settings-form">
        <label>
          导出模式
          <select
            :value="settings.zotero_export_mode"
            @change="updateField('zotero_export_mode', $event.target.value)"
          >
            <option value="prepare">prepare-only</option>
            <option value="connector">connector</option>
            <option value="bridge">bridge</option>
          </select>
        </label>
        <label>
          Zotero Connector URL
          <input
            :value="settings.zotero_connector_url"
            placeholder="http://127.0.0.1:23119"
            type="text"
            @input="updateField('zotero_connector_url', $event.target.value)"
          />
        </label>
        <label>
          Zotero Bridge URL
          <input
            :value="settings.zotero_bridge_url"
            placeholder="Optional local connector bridge endpoint"
            type="text"
            @input="updateField('zotero_bridge_url', $event.target.value || null)"
          />
        </label>
        <label>
          默认 Collection
          <input
            :value="settings.zotero_default_collection"
            placeholder="Optional target collection"
            type="text"
            @input="updateField('zotero_default_collection', $event.target.value || null)"
          />
        </label>
        <label class="checkbox-row">
          <input
            :checked="settings.zotero_include_pdf_by_default"
            type="checkbox"
            @change="updateField('zotero_include_pdf_by_default', $event.target.checked)"
          />
          默认包含 PDF
        </label>
        <label class="checkbox-row">
          <input
            :checked="settings.zotero_include_notes_by_default"
            type="checkbox"
            @change="updateField('zotero_include_notes_by_default', $event.target.checked)"
          />
          默认包含报告 note
        </label>
        <div class="wide mapping-grid">
          <label
            v-for="key in ['Very Important', 'Brief Reading', 'Unrelated', 'Needs Review']"
            :key="key"
          >
            {{ key }} → Collection
            <input
              :value="settings.zotero_collection_mapping?.[key] || key"
              type="text"
              @input="updateCollectionMapping(key, $event.target.value)"
            />
          </label>
        </div>
        <div class="wide actions">
          <button type="button" @click="emit('probe-zotero')">检测 Zotero</button>
          <button type="button" @click="emit('send-zotero-test-payload')">
            发送测试 payload
          </button>
          <button type="button" @click="openZotero">打开 Zotero</button>
          <span>
            {{ zoteroStatus.available ? "Connector 可用" : "Connector 不可用" }}
            {{ zoteroStatus.error ? `· ${zoteroStatus.error}` : "" }}
          </span>
        </div>
        <label v-if="zoteroTestPayload" class="wide">
          测试 payload
          <textarea :value="JSON.stringify(zoteroTestPayload, null, 2)" readonly rows="8"></textarea>
        </label>
        <p class="settings-note">
          PaperReady 不直接修改 Zotero SQLite，不自动删除 Zotero 条目，也不自动合并疑似重复项。
        </p>
      </section>

      <section v-else-if="activeSection === 'privacy'" class="settings-form">
        <dl class="diagnostic-list wide">
          <div><dt>SQLite 数据库</dt><dd>{{ debugInfo.db_path || "未知" }}</dd></div>
          <div><dt>PDF / 报告缓存目录</dt><dd>{{ debugInfo.data_dir || "未知" }}</dd></div>
          <div><dt>当前缓存大小</dt><dd>{{ cacheSize }}</dd></div>
          <div><dt>本地任务数量</dt><dd>{{ debugInfo.task_count || 0 }}</dd></div>
        </dl>
        <p class="settings-note">
          清理缓存不会删除 Zotero 库内容。清理动作需要后端文件管理 API 支撑，当前先展示真实路径与大小。
        </p>
        <button type="button" :disabled="!debugInfo.data_dir" @click="openDataDir">
          打开数据目录
        </button>
        <button type="button" @click="emit('clear-cache', 'failed')">
          清理失败任务缓存
        </button>
        <button type="button" @click="emit('clear-cache', 'exported')">
          清理已导出文章临时文件
        </button>
        <button type="button" @click="pendingClearAll = true">
          清理全部本地缓存
        </button>
      </section>

      <section v-else class="settings-form">
        <p class="settings-note">诊断页用于开发和排错，默认不打扰普通用户。</p>
        <dl class="diagnostic-list wide">
          <div><dt>Backend URL</dt><dd>{{ backendUrl }}</dd></div>
          <div><dt>Worker</dt><dd>{{ workerStatus.running ? "运行中" : "已停止" }}</dd></div>
          <div><dt>Python runtime</dt><dd>conda generic in dev / PyInstaller sidecar in build</dd></div>
          <div><dt>PyInstaller sidecar</dt><dd>构建时打包</dd></div>
          <div><dt>数据库路径</dt><dd>{{ debugInfo.db_path || "未知" }}</dd></div>
          <div><dt>数据目录</dt><dd>{{ debugInfo.data_dir || "未知" }}</dd></div>
          <div><dt>当前 app 版本</dt><dd>{{ appVersion }}</dd></div>
          <div><dt>当前 commit / build id</dt><dd>{{ buildId }}</dd></div>
          <div><dt>Zotero</dt><dd>{{ zoteroStatus.available ? "已连接" : "未连接" }}</dd></div>
          <div><dt>最近错误</dt><dd>{{ workerStatus.last_error || zoteroStatus.error || "无" }}</dd></div>
        </dl>
        <button type="button" @click="emit('restart-backend')">重启 backend</button>
        <button type="button" @click="exportDiagnostics">导出诊断日志</button>
        <button type="button" @click="emit('open-devtools')">打开开发者工具</button>
      </section>

      <div v-if="pendingClearAll" class="sheet-backdrop">
        <section class="sheet">
          <h3>清理全部本地缓存？</h3>
          <p>这会删除 PaperReady 数据目录下的缓存文件，但不会删除 Zotero 库内容。</p>
          <div class="actions">
            <button type="button" @click="pendingClearAll = false">取消</button>
            <button
              type="button"
              class="primary"
              @click="
                pendingClearAll = false;
                emit('clear-cache', 'all');
              "
            >
              清理
            </button>
          </div>
        </section>
      </div>
    </main>
  </section>
</template>
