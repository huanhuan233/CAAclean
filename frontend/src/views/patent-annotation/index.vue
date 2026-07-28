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
const activePdfSourceIds = ref<string[]>([]);
const jsonInputRef = ref<HTMLInputElement | null>(null);
const pdfWorkspaceRef = ref<InstanceType<typeof PdfAnnotationWorkspace> | null>(null);

const currentAnnotations = computed(() =>
  activeSourceId.value ? annotationStore.annotationsFor(activeSourceId.value, activePage.value) : []
);
const activeSource = computed(
  () => annotationStore.document.value.sources.find(item => item.id === activeSourceId.value) ?? null
);
const automationBusy = computed(() => autoAnnotation.parsing.value || autoAnnotation.localizing.value);
const activePdfSources = computed(() =>
  activePdfSourceIds.value
    .map(sourceId => annotationStore.document.value.sources.find(item => item.id === sourceId))
    .filter((source): source is NonNullable<typeof source> => Boolean(source))
);

function handleActiveChange(payload: { sourceId: string; page: number }) {
  activeSourceId.value = payload.sourceId;
  activePage.value = payload.page;
  const selected = annotationStore.selectedAnnotation.value;
  if (selected && (selected.sourceId !== payload.sourceId || selected.page !== payload.page)) {
    annotationStore.selectedAnnotationId.value = '';
  }
}

function handlePdfSourcesChange(sourceIds: string[]) {
  activePdfSourceIds.value = sourceIds;
  autoAnnotation.ensureSourceFigureNos(activePdfSources.value);
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

async function parseAutoPdf(file: File) {
  try {
    const result = await autoAnnotation.parseDocument(file, { sources: activePdfSources.value });
    window.$message?.success(`说明书解析完成：${result.components.length} 个部件，${result.figures.length} 张附图`);
  } catch (error) {
    window.$message?.error(error instanceof Error ? error.message : '说明书 PDF 解析失败');
  }
}

function openFigurePdfPicker() {
  if (automationBusy.value) return;
  pdfWorkspaceRef.value?.openFilePicker();
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
      window.$message?.success(`已生成 ${result.added} 条自动标注，${result.reviewCount} 条待审核`);
    } else {
      window.$message?.info('当前图未识别到可标注部件，原有人工标注已保留');
    }
  } catch (error) {
    window.$message?.error(error instanceof Error ? error.message : '自动标注失败');
  }
}

async function confirmReplaceAutoAnnotations() {
  try {
    await ElMessageBox.confirm('替换当前页旧的自动标注？', '自动标注', {
      type: 'warning',
      confirmButtonText: '替换',
      cancelButtonText: '取消'
    });
    return true;
  } catch {
    return false;
  }
}

function acceptPageAutoAnnotations() {
  if (!activeSourceId.value) return;
  const count = annotationStore.acceptPageAutoAnnotations(activeSourceId.value, activePage.value);
  window.$message?.success(count ? `已接受 ${count} 条自动标注` : '当前页没有待接受的自动标注');
}

async function clearCurrentPage() {
  if (!activeSourceId.value) return;
  try {
    await ElMessageBox.confirm('只会删除当前来源和当前页的标注，是否继续？', '清空当前页', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    });
    annotationStore.clearPage(activeSourceId.value, activePage.value);
    window.$message?.success('当前页标注已清空');
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
    window.$message?.success('标注 JSON 已导入，请重新选择或上传对应源文件以恢复预览');
  } catch (error) {
    const message = error instanceof Error ? error.message : '无法读取标注 JSON';
    window.$message?.error(message);
  }
}

function changeMode(nextMode: string | number | boolean | undefined) {
  if (automationBusy.value) return;
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
        <div class="title-row">
          <div class="page-title">专利附图标注</div>
          <ElTag size="small" effect="plain">自动标注工作台</ElTag>
        </div>
        <div class="page-subtitle">上传说明书提取编号与部件名称，再上传无引线附图自动生成可编辑引线</div>
      </div>
      <ElRadioGroup :model-value="mode" size="small" :disabled="automationBusy" @update:model-value="changeMode">
        <ElRadioButton value="pdf">PDF 附图</ElRadioButton>
        <ElRadioButton value="step">STEP 模型</ElRadioButton>
      </ElRadioGroup>
      <div class="toolbar-spacer" />
      <input ref="jsonInputRef" class="hidden-input" type="file" accept="application/json,.json" @change="importJson" />
      <ElButton :disabled="automationBusy" @click="openJsonImport">导入 JSON</ElButton>
      <ElButton @click="exportJson">导出 JSON</ElButton>
      <ElButton type="danger" plain :disabled="!activeSourceId || automationBusy" @click="clearCurrentPage">
        清空当前页
      </ElButton>
    </header>

    <main class="annotation-shell">
      <section v-if="mode === 'pdf'" class="pdf-column">
        <AutoAnnotationPanel
          :parse-result="autoAnnotation.parseResult.value"
          :parsing="autoAnnotation.parsing.value"
          :localizing="autoAnnotation.localizing.value"
          :progress-text="autoAnnotation.progressText.value"
          :active-source="activeSource"
          :active-page="activePage"
          @parse="parseAutoPdf"
          @upload-figures="openFigurePdfPicker"
          @update-figure="activeSourceId && annotationStore.updateSource(activeSourceId, { figureNo: $event })"
          @localize="localizeCurrentPage"
          @accept-page="acceptPageAutoAnnotations"
        />
        <PdfAnnotationWorkspace
          ref="pdfWorkspaceRef"
          :store="annotationStore"
          :busy="automationBusy"
          @active-change="handleActiveChange"
          @sources-change="handlePdfSourcesChange"
        />
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
  min-height: 62px;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 9px 14px;
  background: var(--el-bg-color);
}

.page-heading {
  min-width: 360px;
  margin-right: 6px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
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
  grid-template-columns: minmax(680px, 1fr) 340px;
  gap: 10px;
}

.pdf-column {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 10px;
}

@media (max-width: 1280px) {
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
