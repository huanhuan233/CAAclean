<script setup lang="ts">
import { computed, ref } from 'vue';
import type { PatentSource } from '../types';

defineOptions({ name: 'PatentAutoAnnotationPanel' });

const props = defineProps<{
  parseResult: Api.PatentAnnotation.DocumentParseResult | null;
  selectedRefs: Set<string>;
  parsing: boolean;
  localizing: boolean;
  progressText: string;
  activeSource: PatentSource | null;
  activePage: number;
}>();

const emit = defineEmits<{
  (event: 'parse', file: File): void;
  (event: 'toggle-ref', refNo: string, selected: boolean): void;
  (event: 'update-component-name', refNo: string, name: string): void;
  (event: 'update-figure', figureNo: string): void;
  (event: 'localize'): void;
  (event: 'accept-page'): void;
}>();

const pdfInputRef = ref<HTMLInputElement | null>(null);
const componentsOpen = ref(true);

const parserLabel = computed(() => {
  if (!props.parseResult) return 'Not parsed';
  return props.parseResult.parser === 'mineru' ? 'MinerU' : 'pypdf fallback';
});
const activeFigure = computed(() => props.parseResult?.figures.find(item => item.figure_no === props.activeSource?.figureNo) ?? null);
const selectedCount = computed(() => props.parseResult?.components.filter(item => props.selectedRefs.has(item.ref_no)).length ?? 0);
const busy = computed(() => props.parsing || props.localizing);

function openPdfInput() {
  pdfInputRef.value?.click();
}

function onPdfSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (file) emit('parse', file);
}
</script>

<template>
  <section class="auto-panel">
    <input ref="pdfInputRef" class="hidden-input" type="file" accept="application/pdf,.pdf" @change="onPdfSelected" />
    <div class="panel-row">
      <ElButton type="primary" plain :loading="parsing" @click="openPdfInput">Parse PDF</ElButton>
      <ElTag size="small" type="info">{{ parserLabel }}</ElTag>
      <span class="summary">
        {{ parseResult?.components.length ?? 0 }} components / {{ parseResult?.figures.length ?? 0 }} figures / page {{ activePage }}
      </span>
    </div>

    <ElAlert
      v-if="parseResult?.warnings.length"
      class="warnings"
      type="warning"
      :closable="false"
      :title="parseResult.warnings.join('; ')"
    />

    <div class="panel-row source-row">
      <span class="file-name">{{ activeSource?.fileName || 'No active PDF source' }}</span>
      <ElSelect
        :model-value="activeSource?.figureNo || ''"
        size="small"
        class="figure-select"
        placeholder="Figure"
        :disabled="!parseResult || !activeSource"
        @change="emit('update-figure', String($event))"
      >
        <ElOption
          v-for="figure in parseResult?.figures ?? []"
          :key="figure.figure_no"
          :label="`Fig. ${figure.figure_no}`"
          :value="figure.figure_no"
        />
      </ElSelect>
    </div>

    <div v-if="activeFigure" class="figure-description">{{ activeFigure.description || `Fig. ${activeFigure.figure_no}` }}</div>

    <button type="button" class="collapse-button" @click="componentsOpen = !componentsOpen">
      <span>Candidate components</span>
      <ElTag size="small">{{ selectedCount }}/{{ parseResult?.components.length ?? 0 }}</ElTag>
    </button>
    <div v-if="componentsOpen" class="component-table">
      <ElEmpty v-if="!parseResult?.components.length" description="Parse a PDF to show components" :image-size="46" />
      <div v-for="component in parseResult?.components ?? []" :key="component.ref_no" class="component-row">
        <ElCheckbox :model-value="selectedRefs.has(component.ref_no)" @change="emit('toggle-ref', component.ref_no, Boolean($event))" />
        <span class="component-ref">{{ component.ref_no }}</span>
        <ElInput
          size="small"
          :model-value="component.name"
          @update:model-value="emit('update-component-name', component.ref_no, String($event))"
        />
      </div>
    </div>

    <div class="panel-actions">
      <ElButton type="primary" :disabled="!parseResult || !activeSource || busy" :loading="localizing" @click="emit('localize')">
        Auto annotate current page
      </ElButton>
      <ElButton :disabled="!activeSource || busy" @click="emit('accept-page')">Accept page auto annotations</ElButton>
    </div>
    <div v-if="progressText" class="progress-text">{{ progressText }}</div>
  </section>
</template>

<style scoped>
.auto-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 10px;
  background: var(--el-bg-color);
}

.hidden-input {
  display: none;
}

.panel-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary,
.file-name,
.figure-description,
.progress-text {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-row {
  min-width: 0;
}

.file-name {
  flex: 1;
}

.figure-select {
  width: 110px;
}

.warnings {
  margin: 2px 0;
}

.collapse-button {
  display: flex;
  min-height: 32px;
  align-items: center;
  justify-content: space-between;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--el-text-color-primary);
  font-weight: 600;
  cursor: pointer;
}

.component-table {
  display: grid;
  max-height: 220px;
  gap: 6px;
  overflow: auto;
}

.component-row {
  display: grid;
  grid-template-columns: 24px 42px 1fr;
  align-items: center;
  gap: 6px;
}

.component-ref {
  color: var(--el-text-color-primary);
  font-weight: 700;
}

.panel-actions {
  display: flex;
  gap: 8px;
}
</style>
