<script setup>
import { STRINGS } from "../strings";

const props = defineProps({
  loading: Boolean,
  settings: { type: Object, required: true },
});
const emit = defineEmits(["save-settings", "update:settings"]);

/** Update one field in the settings model owned by App.vue. */
function updateField(key, value) {
  emit("update:settings", { ...props.settings, [key]: value });
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
</script>

<template>
  <section class="page-card settings-page">
    <header class="page-header">
      <div>
        <h2>{{ STRINGS.settings.title }}</h2>
        <p>Model, budget, and report defaults for the local pipeline.</p>
      </div>
      <button type="button" class="primary" :disabled="loading" @click="emit('save-settings')">
        {{ STRINGS.settings.save }}
      </button>
    </header>

    <div class="settings-grid">
      <label class="wide">
        Research interests
        <textarea
          :value="settings.research_interests"
          rows="5"
          @input="updateField('research_interests', $event.target.value)"
        />
      </label>
      <label>
        Batch budget
        <input
          :value="settings.batch_budget"
          type="number"
          min="0"
          step="0.01"
          @input="updateField('batch_budget', Number($event.target.value))"
        />
      </label>
      <label>
        Daily budget
        <input
          :value="settings.daily_budget"
          type="number"
          min="0"
          step="0.01"
          @input="updateField('daily_budget', Number($event.target.value) || null)"
        />
      </label>
      <label>
        Monthly budget
        <input
          :value="settings.monthly_budget"
          type="number"
          min="0"
          step="0.01"
          @input="updateField('monthly_budget', Number($event.target.value) || null)"
        />
      </label>
      <label>
        API base URL
        <input
          :value="settings.llm_api_base_url"
          type="text"
          @input="updateField('llm_api_base_url', $event.target.value)"
        />
      </label>
      <label>
        API key
        <input
          :value="settings.api_key"
          type="password"
          autocomplete="off"
          placeholder="Stored locally for configured provider"
          @input="updateField('api_key', $event.target.value)"
        />
      </label>
      <label>
        Locator model
        <input
          :value="settings.locating_model"
          type="text"
          @input="updateField('locating_model', $event.target.value)"
        />
      </label>
      <label>
        Evaluation model
        <input
          :value="settings.evaluation_model"
          type="text"
          @input="updateField('evaluation_model', $event.target.value)"
        />
      </label>
      <label>
        Summary model
        <input
          :value="settings.summarization_model"
          type="text"
          @input="updateField('summarization_model', $event.target.value)"
        />
      </label>
      <label>
        Default report
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
        Locator concurrency
        <input
          :value="settings.locating_concurrency"
          type="number"
          min="1"
          @input="updateField('locating_concurrency', Number($event.target.value))"
        />
      </label>
      <label>
        Evaluation concurrency
        <input
          :value="settings.evaluation_concurrency"
          type="number"
          min="1"
          @input="updateField('evaluation_concurrency', Number($event.target.value))"
        />
      </label>
      <label>
        Summary concurrency
        <input
          :value="settings.summarization_concurrency"
          type="number"
          min="1"
          @input="updateField('summarization_concurrency', Number($event.target.value))"
        />
      </label>
      <label>
        Budget overflow
        <select
          :value="settings.budget_overflow_behavior"
          @change="updateField('budget_overflow_behavior', $event.target.value)"
        >
          <option value="pause">Pause and ask</option>
          <option value="deny">Deny automatically</option>
        </select>
      </label>
      <label>
        Language placeholder
        <select
          :value="settings.language_preference"
          @change="updateField('language_preference', $event.target.value)"
        >
          <option value="en">English</option>
          <option value="zh">Chinese placeholder</option>
        </select>
      </label>
      <label>
        Zotero bridge URL
        <input
          :value="settings.zotero_bridge_url"
          type="text"
          placeholder="Optional local connector bridge endpoint"
          @input="updateField('zotero_bridge_url', $event.target.value || null)"
        />
      </label>
      <label class="checkbox-row">
        <input
          :checked="settings.yolo_default"
          type="checkbox"
          @change="updateField('yolo_default', $event.target.checked)"
        />
        Enable YOLO mode by default
      </label>
      <label class="wide">
        Report types JSON
        <textarea
          :value="formatJson(settings.report_types)"
          rows="8"
          @change="updateJsonField('report_types', $event.target.value)"
        />
      </label>
      <label class="wide">
        Prompt templates JSON
        <textarea
          :value="formatJson(settings.prompt_templates)"
          rows="8"
          @change="updateJsonField('prompt_templates', $event.target.value)"
        />
      </label>
    </div>
  </section>
</template>
