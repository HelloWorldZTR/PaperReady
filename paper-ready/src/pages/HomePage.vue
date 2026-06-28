<script setup>
import { ref } from "vue";
import { STRINGS } from "../strings";

const props = defineProps({
  loading: Boolean,
});
const emit = defineEmits(["create-tasks"]);
const batchInput = ref("2401.12345\n10.1145/1234567\nA Useful Paper Title");
const isDragging = ref(false);

/** Submit text and dropped PDF paths as new queue inputs. */
function submit() {
  emit("create-tasks", batchInput.value);
}

/** Add dropped PDF file paths or names to the batch input. */
function handleDrop(event) {
  isDragging.value = false;
  const files = [...(event.dataTransfer?.files || [])];
  const pdfs = files
    .filter((file) => file.name.toLowerCase().endsWith(".pdf"))
    .map((file) => file.path || file.webkitRelativePath || file.name);
  if (pdfs.length === 0) {
    return;
  }
  const current = batchInput.value.trim();
  batchInput.value = [current, ...pdfs].filter(Boolean).join("\n");
}
</script>

<template>
  <section class="home-page">
    <div class="home-input">
      <textarea
        v-model="batchInput"
        :placeholder="STRINGS.home.inputPlaceholder"
        rows="10"
        @keydown.meta.enter.prevent="submit"
        @keydown.ctrl.enter.prevent="submit"
      />
      <button type="button" class="primary" :disabled="props.loading" @click="submit">
        {{ STRINGS.home.start }}
      </button>
    </div>

    <div
      class="drop-zone"
      :class="{ dragging: isDragging }"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="drop-icon">PDF</div>
      <strong>{{ STRINGS.home.dropTitle }}</strong>
      <span>{{ STRINGS.home.dropHint }}</span>
    </div>
  </section>
</template>

