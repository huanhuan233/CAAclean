<script setup lang="ts">
import { computed, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import { usePatentAnnotations } from './composables/usePatentAnnotations';
import AnnotationInspector from './modules/AnnotationInspector.vue';
import PdfAnnotationWorkspace from './modules/PdfAnnotationWorkspace.vue';
import type { PatentAnnotation, SourceKind } from './types';

defineOptions({ name: 'PatentAnnotationPage' });

const annotationStore = usePatentAnnotations();
const mode = ref<SourceKind>('pdf');
const activeSourceId = ref('');
const activePage = ref(1);
const jsonInputRef = ref<HTMLInputElement | null>(null);

const currentAnnotations = computed(() =>
  activeSourceId.value ? annotationStore.annotationsFor(activeSourceId.value, activePage.value) : []
);

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
    window.$message?.success('标注 JSON 已导入，请重新上传对应 PDF 以恢复预览');
  } catch (error) {
    const message = error instanceof Error ? error.message : '无法读取标注 JSON';
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
        <div class="page-title">专利附图标注</div>
        <div class="page-subtitle">手工建立稳定的引线标注数据</div>
      </div>
      <ElRadioGroup :model-value="mode" size="small" @update:model-value="changeMode">
        <ElRadioButton value="pdf">PDF 附图</ElRadioButton>
        <ElRadioButton value="step" disabled>STEP 模型</ElRadioButton>
      </ElRadioGroup>
      <div class="toolbar-spacer" />
      <input ref="jsonInputRef" class="hidden-input" type="file" accept="application/json,.json" @change="importJson" />
      <ElButton @click="openJsonImport">导入 JSON</ElButton>
      <ElButton @click="exportJson">导出 JSON</ElButton>
      <ElButton type="danger" plain :disabled="!activeSourceId" @click="clearCurrentPage">清空当前页</ElButton>
    </header>

    <main class="annotation-shell">
      <PdfAnnotationWorkspace v-if="mode === 'pdf'" :store="annotationStore" @active-change="handleActiveChange" />
      <ElEmpty v-else description="STEP 标注模式将在下一阶段接入" />
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
