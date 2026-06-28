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
        API base URL
        <input
          :value="settings.llm_api_base_url"
          type="text"
          @input="updateField('llm_api_base_url', $event.target.value)"
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
    </div>
  </section>
</template>

