<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';
import type { UploadRequestOptions } from 'element-plus';
import { fetchCadMeshes, fetchCadModels, fetchCadRevisionStatus, uploadCadModel } from '@/service/api';
import CadViewer from '@/views/cad-model/modules/CadViewer.vue';
import type { CadSceneClick } from '@/views/cad-model/modules/cad-viewer-interaction';
import type { PatentAnnotationStore } from '../composables/usePatentAnnotations';
import { isStepFileName, revisionAction, shouldLockStepView } from '../step-runtime';
import type { AnnotationPointUpdate } from '../types';
import LeaderOverlay from './LeaderOverlay.vue';

defineOptions({ name: 'StepAnnotationWorkspace' });

const props = defineProps<{
  store: PatentAnnotationStore;
}>();
const store = props.store;

const emit = defineEmits<{
  (event: 'activeChange', payload: { sourceId: string; page: number }): void;
}>();

const models = ref<Api.Cad.ModelSummary[]>([]);
const selectedModelId = ref('');
const selectedRevisionId = ref('');
const status = ref<Api.Cad.ParseStatus | null>(null);
const meshes = ref<Api.Cad.Mesh[]>([]);
const loadingModels = ref(false);
const loadingMeshes = ref(false);
const uploading = ref(false);
const pollTimer = ref<number | null>(null);
const pollingRequest = ref(false);
const cameraLocked = ref(false);
const addPending = ref(false);
const activeSourceId = ref('');
const stageRef = ref<HTMLDivElement | null>(null);
const stageWidth = ref(1);
const stageHeight = ref(1);
let resizeObserver: ResizeObserver | null = null;

const selectedModel = computed(() => models.value.find(item => item.id === selectedModelId.value) ?? null);
const activeSource = computed(
  () => store.document.value.sources.find(item => item.id === activeSourceId.value) ?? null
);
const currentAnnotations = computed(() => (activeSourceId.value ? store.annotationsFor(activeSourceId.value, 1) : []));
const selectedFaceId = computed(() => {
  const annotation = store.selectedAnnotation.value;
  return annotation?.sourceId === activeSourceId.value ? (annotation.entityId ?? '') : '';
});
const isProcessing = computed(() => revisionAction(status.value?.status ?? 'deleted') === 'poll');
const progress = computed(() =>
  Math.min(100, Math.max(0, status.value?.progress ?? selectedModel.value?.progress ?? 0))
);
const statusText = computed(() => {
  if (status.value?.status === 'completed') return '解析完成';
  if (status.value?.status === 'failed') return '解析失败';
  if (status.value?.status === 'processing') return '解析中';
  if (status.value?.status === 'queued') return '排队中';
  if (status.value?.status === 'uploaded') return '已上传';
  if (selectedRevisionId.value) return '等待解析';
  return '未选择';
});
const statusTagType = computed(() => {
  if (status.value?.status === 'completed') return 'success';
  if (status.value?.status === 'failed' || status.value?.status === 'deleted') return 'danger';
  return 'info';
});
const canAdd = computed(() =>
  Boolean(activeSource.value && meshes.value.length && status.value?.status === 'completed')
);

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
  pollingRequest.value = false;
}

function startPolling() {
  if (pollTimer.value !== null || !selectedRevisionId.value) return;
  pollTimer.value = window.setInterval(() => {
    runAsync(loadStatus(selectedRevisionId.value));
  }, 1500);
}

async function loadModels(selectFirst = true) {
  loadingModels.value = true;
  try {
    const result = await fetchCadModels({ page: 1, page_size: 50 });
    if (result.error || !result.data) return;
    models.value = result.data.items;
    if (selectFirst && !selectedModelId.value && models.value.length > 0) {
      await activateModel(models.value[0]);
    }
  } finally {
    loadingModels.value = false;
  }
}

function refreshModels() {
  runAsync(loadModels(false));
}

function selectModelById(modelId: string) {
  const model = models.value.find(item => item.id === modelId);
  if (model) runAsync(activateModel(model));
}

async function activateModel(model: Api.Cad.ModelSummary) {
  stopPolling();
  selectedModelId.value = model.id;
  selectedRevisionId.value = model.current_revision_id ?? '';
  status.value = null;
  meshes.value = [];
  activeSourceId.value = '';
  cameraLocked.value = false;
  addPending.value = false;
  store.selectedAnnotationId.value = '';

  if (!selectedRevisionId.value) {
    emit('activeChange', { sourceId: '', page: 1 });
    return;
  }

  bindSource(model.name, selectedRevisionId.value);
  await loadStatus(selectedRevisionId.value);
}

function bindSource(fileName: string, revisionId: string) {
  const source = store.getOrCreateSource({
    kind: 'step',
    fileKey: `cad-revision:${revisionId}`,
    fileName,
    pageCount: 1
  });
  activeSourceId.value = source.id;
  cameraLocked.value = shouldLockStepView(store.annotationsFor(source.id, 1).length);
  emit('activeChange', { sourceId: source.id, page: 1 });
}

async function loadStatus(revisionId: string) {
  if (!revisionId || revisionId !== selectedRevisionId.value || pollingRequest.value) return;
  pollingRequest.value = true;
  try {
    const result = await fetchCadRevisionStatus(revisionId);
    if (revisionId !== selectedRevisionId.value) return;
    const action = revisionAction(result.data?.status, Boolean(result.error || !result.data));
    if (result.error || !result.data) {
      stopPolling();
      const message = result.error instanceof Error ? result.error.message : 'STEP 状态获取失败';
      window.$message?.error(message);
      return;
    }
    status.value = result.data;
    if (action === 'load') {
      stopPolling();
      await loadMeshes(revisionId);
      return;
    }
    if (action === 'poll') {
      startPolling();
      return;
    }

    stopPolling();
    if (result.data.status === 'failed') {
      window.$message?.error(result.data.error_message || result.data.status_message || 'STEP 解析失败');
    }
  } finally {
    pollingRequest.value = false;
  }
}

async function loadMeshes(revisionId: string) {
  loadingMeshes.value = true;
  try {
    const result = await fetchCadMeshes(revisionId, { page: 1, page_size: 5000 });
    if (revisionId !== selectedRevisionId.value || result.error || !result.data) return;
    meshes.value = result.data.items;
  } finally {
    if (revisionId === selectedRevisionId.value) loadingMeshes.value = false;
  }
}

function beforeUpload(file: File) {
  const accepted = isStepFileName(file.name);
  if (!accepted) window.$message?.error('只支持 STEP/STP 文件');
  return accepted;
}

async function handleUpload(options: UploadRequestOptions) {
  const file = options.file;
  uploading.value = true;
  try {
    const result = await uploadCadModel(file, file.name.replace(/\.(step|stp)$/i, ''));
    if (result.error || !result.data) throw new Error('STEP 上传失败');

    stopPolling();
    selectedModelId.value = result.data.model_id;
    selectedRevisionId.value = result.data.revision_id;
    status.value = {
      status: result.data.status,
      progress: 0,
      status_message: '等待解析',
      error_code: null,
      error_message: null
    };
    meshes.value = [];
    cameraLocked.value = false;
    addPending.value = false;
    store.selectedAnnotationId.value = '';
    bindSource(file.name.replace(/\.(step|stp)$/i, ''), result.data.revision_id);
    await loadModels(false);
    startPolling();
    options.onSuccess(result.data);
  } catch (error) {
    const uploadError = error instanceof Error ? error : new Error('STEP 上传失败');
    window.$message?.error(uploadError.message);
    options.onError(uploadError as Parameters<typeof options.onError>[0]);
  } finally {
    uploading.value = false;
  }
}

function beginAdd() {
  if (!canAdd.value) return;
  cameraLocked.value = true;
  addPending.value = true;
}

function handleSceneClick(payload: CadSceneClick) {
  if (!addPending.value || !activeSource.value) return;
  const annotation = store.createAnnotation({
    sourceId: activeSource.value.id,
    sourceKind: 'step',
    page: 1,
    anchor: payload.screen,
    entityId: payload.entityId,
    worldPoint: payload.worldPoint
  });
  store.selectedAnnotationId.value = annotation.id;
  addPending.value = false;
  cameraLocked.value = true;
}

async function requestUnlock() {
  if (!cameraLocked.value) return;
  if (activeSource.value && currentAnnotations.value.length > 0) {
    try {
      await ElMessageBox.confirm('解锁视角会清空当前 STEP 视图的全部标注，是否继续？', '解锁视角', {
        type: 'warning',
        confirmButtonText: '解锁并清空',
        cancelButtonText: '取消'
      });
    } catch {
      return;
    }
    store.clearSource(activeSource.value.id);
  }

  cameraLocked.value = false;
  addPending.value = false;
}

function selectAnnotation(annotationId: string) {
  store.selectedAnnotationId.value = annotationId;
}

function updateLeaderPoint(payload: AnnotationPointUpdate) {
  store.updateAnnotation(payload.id, { [payload.point]: payload.value });
}

function resizeStage() {
  const stage = stageRef.value;
  if (!stage) return;
  stageWidth.value = Math.max(stage.clientWidth, 1);
  stageHeight.value = Math.max(stage.clientHeight, 1);
}

function runAsync(task: Promise<unknown>) {
  task.catch(error => {
    const message = error instanceof Error ? error.message : 'STEP 操作失败';
    window.$message?.error(message);
  });
}

onMounted(() => {
  resizeStage();
  if (stageRef.value) {
    resizeObserver = new ResizeObserver(resizeStage);
    resizeObserver.observe(stageRef.value);
  }
  runAsync(loadModels());
});

onBeforeUnmount(() => {
  stopPolling();
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <section class="step-workspace">
    <div class="workspace-toolbar">
      <ElUpload
        :show-file-list="false"
        :http-request="handleUpload"
        :before-upload="beforeUpload"
        :disabled="uploading"
        accept=".step,.stp"
      >
        <ElButton type="primary" plain :loading="uploading">上传 STEP</ElButton>
      </ElUpload>
      <ElSelect
        :model-value="selectedModelId"
        class="model-select"
        filterable
        placeholder="选择 STEP 模型"
        :disabled="loadingModels || !models.length"
        @change="selectModelById"
      >
        <ElOption
          v-for="model in models"
          :key="model.id"
          :label="`${model.name} · ${model.status ?? 'unknown'}`"
          :value="model.id"
        />
      </ElSelect>
      <ElButton :loading="loadingModels" @click="refreshModels">刷新模型</ElButton>
      <ElTag :type="statusTagType">{{ statusText }}</ElTag>
      <ElProgress v-if="isProcessing" :percentage="progress" :stroke-width="8" class="status-progress" />
      <div class="toolbar-spacer" />
      <ElButton :type="addPending ? 'primary' : 'default'" :disabled="!canAdd" @click="beginAdd">
        {{ addPending ? '点击模型表面放置引线' : cameraLocked ? '继续添加引线' : '锁定视角并添加引线' }}
      </ElButton>
      <ElButton :disabled="!cameraLocked" @click="requestUnlock">解锁视角</ElButton>
    </div>

    <div ref="stageRef" v-loading="loadingMeshes" class="viewer-stage" :class="{ 'add-pending': addPending }">
      <CadViewer
        :meshes="meshes"
        :selected-face-id="selectedFaceId"
        :camera-locked="cameraLocked"
        @scene-click="handleSceneClick"
      />
      <LeaderOverlay
        v-if="activeSource"
        pass-through
        :annotations="currentAnnotations"
        :selected-id="store.selectedAnnotationId.value"
        :stage-width="stageWidth"
        :stage-height="stageHeight"
        @select="selectAnnotation"
        @update="updateLeaderPoint"
      />
      <div v-if="addPending" class="interaction-hint">视角已锁定，点击零件表面放置引线</div>
      <div v-else-if="cameraLocked" class="interaction-hint">视角已锁定，引线位置可拖动编辑</div>
    </div>
  </section>
</template>

<style scoped>
.step-workspace {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.workspace-toolbar {
  display: flex;
  min-height: 50px;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 8px 10px;
  white-space: nowrap;
}

.model-select {
  width: 260px;
  flex: 0 0 auto;
}

.status-progress {
  width: 120px;
  flex: 0 0 auto;
}

.toolbar-spacer {
  min-width: 12px;
  flex: 1;
}

.viewer-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  flex: 1;
  overflow: hidden;
  background: #f7f9fc;
}

.viewer-stage.add-pending {
  cursor: crosshair;
}

.viewer-stage :deep(.cad-viewer) {
  height: 100%;
  min-height: 0;
  border: 0;
  border-radius: 0;
}

.interaction-hint {
  position: absolute;
  z-index: 3;
  right: 12px;
  bottom: 12px;
  border-radius: 4px;
  padding: 6px 10px;
  background: rgb(17 24 39 / 72%);
  color: #fff;
  font-size: 12px;
  pointer-events: none;
}
</style>
