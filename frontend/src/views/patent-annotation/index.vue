<script setup lang="ts">
import { computed, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import { usePatentAutoAnnotation } from './composables/usePatentAutoAnnotation';
import { usePatentAnnotations } from './composables/usePatentAnnotations';
import AnnotationInspector from './modules/AnnotationInspector.vue';
import AutoAnnotationPanel from './modules/AutoAnnotationPanel.vue';
import PdfAnnotationWorkspace from './modules/PdfAnnotationWorkspace.vue';
import StepAnnotationWorkspace from './modules/StepAnnotationWorkspace.vue';
import type { PatentAnnotation, SourceKind } from './types';

defineOptions({ name: 'PatentAnnotationPage' });

const annotationStore = usePatentAnnotations();
const autoAnnotation = usePatentAutoAnnotation(annotationStore);
const mode = ref<SourceKind>('pdf');
const activeSourceId = ref('');
const activePage = ref(1);
const jsonInputRef = ref<HTMLInputElement | null>(null);
const pdfWorkspaceRef = ref<InstanceType<typeof PdfAnnotationWorkspace> | null>(null);

const currentAnnotations = computed(() =>
  activeSourceId.value ? annotationStore.annotationsFor(activeSourceId.value, activePage.value) : []
);
const activeSource = computed(() => annotationStore.document.value.sources.find(item => item.id === activeSourceId.value) ?? null);

function handleActiveChange(payload: { sourceId: string; page: number }) {
  activeSourceId.value = payload.sourceId;
  activePage.value = payload.page;
  const selected = annotationStore.selectedAnnotation.value;
  if (selected && (selected.sourceId !== payload.sourceId || selected.page !== payload.page)) {
    annotationStore.selectedAnnotationId.value = '';
  }
}

function selectAnnotation(annotationId: string) {
  annotationStore.selectedAnnotationId.value = annotationId;
}

function updateAnnotation(annotationId: string, patch: Partial<PatentAnnotation>) {
  annotationStore.updateAnnotation(annotationId, patch);
}

function deleteAnnotation(annotationId: string) {
  annotationStore.removeAnnotation(annotationId);
}

function toggleRef(refNo: string, selected: boolean) {
  const next = new Set(autoAnnotation.selectedRefs.value);
  if (selected) next.add(refNo);
  else next.delete(refNo);
  autoAnnotation.selectedRefs.value = next;
}

async function parseAutoPdf(file: File) {
  try {
    await autoAnnotation.parseDocument(file);
    window.$message?.success('PDF parsed');
  } catch (error) {
    window.$message?.error(error instanceof Error ? error.message : 'PDF parse failed');
  }
}

async function localizeCurrentPage() {
  if (!pdfWorkspaceRef.value || !activeSourceId.value) return;
  try {
    const result = await autoAnnotation.localizeCurrentPage({
      workspace: pdfWorkspaceRef.value,
      sourceId: activeSourceId.value,
      page: activePage.value,
      confirmReplace: confirmReplaceAutoAnnotations
    });
    if (result.added) {
      window.$message?.success(`Created ${result.added} auto annotations, ${result.reviewCount} need review`);
    } else {
      window.$message?.info('No new auto annotations were created');
    }
  } catch (error) {
    window.$message?.error(error instanceof Error ? error.message : 'Auto annotation failed');
  }
}

async function confirmReplaceAutoAnnotations() {
  try {
    await ElMessageBox.confirm('Replace existing automatic annotations on this page?', 'Auto annotation', {
      type: 'warning',
      confirmButtonText: 'Replace',
      cancelButtonText: 'Cancel'
    });
    return true;
  } catch {
    return false;
  }
}

function acceptPageAutoAnnotations() {
  if (!activeSourceId.value) return;
  const count = annotationStore.acceptPageAutoAnnotations(activeSourceId.value, activePage.value);
  window.$message?.success(count ? `Accepted ${count} automatic annotations` : 'No pending automatic annotations on this page');
}

async function clearCurrentPage() {
  if (!activeSourceId.value) return;
  try {
    await ElMessageBox.confirm('Only annotations for the current source and page will be deleted. Continue?', 'Clear current page', {
      type: 'warning',
      confirmButtonText: 'Clear',
      cancelButtonText: 'Cancel'
    });
    annotationStore.clearPage(activeSourceId.value, activePage.value);
    window.$message?.success('Current page annotations cleared');
  } catch {
    // The user cancelled the destructive action.
  }
}

function exportJson() {
  const blob = new Blob([JSON.stringify(annotationStore.exportDocument(), null, 2)], {
    type: 'application/json'
  });
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = 'patent-annotations.json';
  anchor.click();
  URL.revokeObjectURL(url);
}

function openJsonImport() {
  jsonInputRef.value?.click();
}

async function importJson(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;

  try {
    const raw = await file.text();
    annotationStore.replaceDocument(JSON.parse(raw));
    activeSourceId.value = '';
    activePage.value = 1;
    window.$message?.success('Annotation JSON imported. Reopen the source file to restore preview.');
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to read annotation JSON';
    window.$message?.error(message);
  }
}

function changeMode(nextMode: string | number | boolean | undefined) {
  if (nextMode !== 'pdf' && nextMode !== 'step') return;
  mode.value = nextMode;
  activeSourceId.value = '';
  activePage.value = 1;
  annotationStore.selectedAnnotationId.value = '';
}
</script>

<template>
  <div class="patent-annotation-page">
    <header class="page-toolbar">
      <div class="page-heading">
        <div class="page-title">Patent figure annotation</div>
        <div class="page-subtitle">Build stable leader-line annotations for patent figures</div>
      </div>
      <ElRadioGroup :model-value="mode" size="small" @update:model-value="changeMode">
        <ElRadioButton value="pdf">PDF figures</ElRadioButton>
        <ElRadioButton value="step">STEP model</ElRadioButton>
      </ElRadioGroup>
      <div class="toolbar-spacer" />
      <input ref="jsonInputRef" class="hidden-input" type="file" accept="application/json,.json" @change="importJson" />
      <ElButton @click="openJsonImport">Import JSON</ElButton>
      <ElButton @click="exportJson">Export JSON</ElButton>
      <ElButton type="danger" plain :disabled="!activeSourceId" @click="clearCurrentPage">Clear current page</ElButton>
    </header>

    <main class="annotation-shell">
      <section v-if="mode === 'pdf'" class="pdf-column">
        <AutoAnnotationPanel
          :parse-result="autoAnnotation.parseResult.value"
          :selected-refs="autoAnnotation.selectedRefs.value"
          :parsing="autoAnnotation.parsing.value"
          :localizing="autoAnnotation.localizing.value"
          :progress-text="autoAnnotation.progressText.value"
          :active-source="activeSource"
          :active-page="activePage"
          @parse="parseAutoPdf"
          @toggle-ref="toggleRef"
          @update-component-name="autoAnnotation.updateComponentName"
          @update-figure="activeSourceId && annotationStore.updateSource(activeSourceId, { figureNo: $event })"
          @localize="localizeCurrentPage"
          @accept-page="acceptPageAutoAnnotations"
        />
        <PdfAnnotationWorkspace ref="pdfWorkspaceRef" :store="annotationStore" @active-change="handleActiveChange" />
      </section>
      <StepAnnotationWorkspace v-else :store="annotationStore" @active-change="handleActiveChange" />
      <AnnotationInspector
        :annotations="currentAnnotations"
        :selected-annotation="annotationStore.selectedAnnotation.value"
        @select="selectAnnotation"
        @update="updateAnnotation"
        @delete="deleteAnnotation"
      />
    </main>
  </div>
</template>

<style scoped>
.patent-annotation-page {
  display: flex;
  height: calc(100vh - 96px);
  min-height: 680px;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.page-toolbar {
  display: flex;
  min-height: 54px;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--el-bg-color);
}

.page-heading {
  min-width: 180px;
  margin-right: 6px;
}

.page-title {
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 700;
}

.page-subtitle {
  margin-top: 2px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.toolbar-spacer {
  min-width: 12px;
  flex: 1;
}

.hidden-input {
  display: none;
}

.annotation-shell {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(620px, 1fr) 360px;
  gap: 10px;
}

.pdf-column {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 10px;
}

@media (max-width: 1100px) {
  .patent-annotation-page {
    height: auto;
    min-height: 0;
    overflow: visible;
  }

  .page-toolbar {
    flex-wrap: wrap;
  }

  .toolbar-spacer {
    display: none;
  }

  .annotation-shell {
    display: flex;
    flex-direction: column;
  }

  .annotation-shell > :first-child {
    min-height: 620px;
  }

  .annotation-shell > :last-child {
    min-height: 620px;
  }
}
</style>
