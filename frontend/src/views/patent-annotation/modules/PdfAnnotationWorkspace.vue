<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import VuePdfEmbed from 'vue-pdf-embed';
import type { PatentAnnotationStore } from '../composables/usePatentAnnotations';
import { clientPointToNormalized } from '../geometry';
import type { AnnotationPointUpdate } from '../types';
import LeaderOverlay from './LeaderOverlay.vue';

defineOptions({ name: 'PdfAnnotationWorkspace' });

const props = withDefaults(
  defineProps<{
    store: PatentAnnotationStore;
    busy?: boolean;
  }>(),
  {
    busy: false
  }
);
const store = props.store;

const emit = defineEmits<{
  (event: 'activeChange', payload: { sourceId: string; page: number }): void;
  (event: 'sourcesChange', sourceIds: string[]): void;
}>();

interface PdfRuntimeSource {
  sourceId: string;
  fileKey: string;
  file: File;
  objectUrl: string;
}

interface PanState {
  pointerId: number;
  clientX: number;
  clientY: number;
  panX: number;
  panY: number;
}

const fileInputRef = ref<HTMLInputElement | null>(null);
const viewportRef = ref<HTMLDivElement | null>(null);
const stageRef = ref<HTMLDivElement | null>(null);
const pdfRef = shallowRef<InstanceType<typeof VuePdfEmbed> | null>(null);
const runtimeSources = ref<PdfRuntimeSource[]>([]);
const activeSourceId = ref('');
const currentPage = ref(1);
const stageWidth = ref(1);
const stageHeight = ref(1);
const zoom = ref(1);
const panX = ref(0);
const panY = ref(0);
const addMode = ref(false);
const spacePressed = ref(false);
const panning = ref(false);
const panState = ref<PanState | null>(null);
const PDF_CAPTURE_UNAVAILABLE = '当前 PDF 页尚未渲染';

const activeRuntime = computed(() => runtimeSources.value.find(item => item.sourceId === activeSourceId.value) ?? null);
const activeSource = computed(
  () => props.store.document.value.sources.find(item => item.id === activeSourceId.value) ?? null
);
const pageCount = computed(() => activeSource.value?.pageCount ?? 1);
const currentAnnotations = computed(() =>
  activeSourceId.value ? props.store.annotationsFor(activeSourceId.value, currentPage.value) : []
);
const stageStyle = computed(() => ({
  width: `${stageWidth.value}px`,
  height: `${stageHeight.value}px`,
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`
}));

function openFilePicker() {
  if (props.busy) return;
  fileInputRef.value?.click();
}

function handleFileSelection(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = '';
  if (props.busy) return;
  addPdfFiles(files);
}

function addPdfFiles(files: File[]) {
  let accepted = false;
  for (const file of files) {
    if (file.type !== 'application/pdf' && !/\.pdf$/i.test(file.name)) {
      window.$message?.error(`${file.name} 不是 PDF 文件`);
    } else {
      accepted = true;
      const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
      const source = store.getOrCreateSource({
        kind: 'pdf',
        fileKey,
        fileName: file.name,
        pageCount: 1
      });
      const existing = runtimeSources.value.find(item => item.fileKey === fileKey);
      if (existing) {
        activeSourceId.value = existing.sourceId;
      } else {
        runtimeSources.value.push({
          sourceId: source.id,
          fileKey,
          file,
          objectUrl: URL.createObjectURL(file)
        });
        activeSourceId.value ||= source.id;
      }
    }
  }

  if (files.length > 0 && activeSourceId.value) {
    const lastAccepted = [...runtimeSources.value]
      .reverse()
      .find(item => files.some(file => `${file.name}:${file.size}:${file.lastModified}` === item.fileKey));
    if (lastAccepted) activeSourceId.value = lastAccepted.sourceId;
  }
  if (accepted) emitRuntimeSources();
}

function removeActiveFile() {
  if (props.busy) return;
  const index = runtimeSources.value.findIndex(item => item.sourceId === activeSourceId.value);
  if (index < 0) return;
  const [removed] = runtimeSources.value.splice(index, 1);
  URL.revokeObjectURL(removed.objectUrl);
  const next = runtimeSources.value[Math.min(index, runtimeSources.value.length - 1)];
  activeSourceId.value = next?.sourceId ?? '';
  emitRuntimeSources();
}

function selectSource(sourceId: string) {
  if (props.busy) return;
  activeSourceId.value = sourceId;
}

function emitRuntimeSources() {
  emit(
    'sourcesChange',
    runtimeSources.value.map(item => item.sourceId)
  );
}

async function onPdfRendered() {
  const count = Number(pdfRef.value?.doc?.numPages ?? 1);
  if (activeSourceId.value && Number.isFinite(count)) {
    store.updateSource(activeSourceId.value, { pageCount: count });
    currentPage.value = Math.min(currentPage.value, count);
  }

  await nextTick();
  const canvas = stageRef.value?.querySelector('canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  stageWidth.value = Math.max(canvas.clientWidth || rect.width / zoom.value, 1);
  stageHeight.value = Math.max(canvas.clientHeight || rect.height / zoom.value, 1);
  await nextTick();
  fitStage();
}

function fitStage() {
  const viewport = viewportRef.value;
  if (!viewport || !activeRuntime.value || stageWidth.value <= 0 || stageHeight.value <= 0) return;
  const scaleX = (viewport.clientWidth - 32) / stageWidth.value;
  const scaleY = (viewport.clientHeight - 32) / stageHeight.value;
  zoom.value = Math.min(6, Math.max(0.1, Math.min(scaleX, scaleY)));
  panX.value = Math.max(16, (viewport.clientWidth - stageWidth.value * zoom.value) / 2);
  panY.value = Math.max(16, (viewport.clientHeight - stageHeight.value * zoom.value) / 2);
}

function zoomBy(factor: number, clientX?: number, clientY?: number) {
  const viewport = viewportRef.value;
  if (!viewport || !activeRuntime.value) return;
  const oldZoom = zoom.value;
  const nextZoom = Math.min(6, Math.max(0.1, oldZoom * factor));
  if (nextZoom === oldZoom) return;

  const rect = viewport.getBoundingClientRect();
  const pivotX = clientX ?? rect.left + viewport.clientWidth / 2;
  const pivotY = clientY ?? rect.top + viewport.clientHeight / 2;
  const stageX = (pivotX - rect.left - panX.value) / oldZoom;
  const stageY = (pivotY - rect.top - panY.value) / oldZoom;
  panX.value = pivotX - rect.left - stageX * nextZoom;
  panY.value = pivotY - rect.top - stageY * nextZoom;
  zoom.value = nextZoom;
}

function onWheel(event: WheelEvent) {
  zoomBy(event.deltaY > 0 ? 1 / 1.1 : 1.1, event.clientX, event.clientY);
}

function startPan(event: PointerEvent) {
  const shouldPan = event.button === 1 || (event.button === 0 && spacePressed.value);
  const viewport = viewportRef.value;
  if (!shouldPan || !viewport || !activeRuntime.value) return;
  event.preventDefault();
  viewport.setPointerCapture(event.pointerId);
  panning.value = true;
  panState.value = {
    pointerId: event.pointerId,
    clientX: event.clientX,
    clientY: event.clientY,
    panX: panX.value,
    panY: panY.value
  };
}

function movePan(event: PointerEvent) {
  const state = panState.value;
  if (!state || state.pointerId !== event.pointerId) return;
  panX.value = state.panX + event.clientX - state.clientX;
  panY.value = state.panY + event.clientY - state.clientY;
}

function stopPan(event: PointerEvent) {
  const state = panState.value;
  const viewport = viewportRef.value;
  if (!state || state.pointerId !== event.pointerId) return;
  if (viewport?.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  panState.value = null;
  panning.value = false;
}

function onStagePointerDown(event: PointerEvent) {
  if (!addMode.value || event.button !== 0 || spacePressed.value || !activeSource.value || !stageRef.value) return;
  event.preventDefault();
  const annotation = store.createAnnotation({
    sourceId: activeSource.value.id,
    sourceKind: 'pdf',
    page: currentPage.value,
    anchor: clientPointToNormalized(event.clientX, event.clientY, stageRef.value.getBoundingClientRect())
  });
  store.selectedAnnotationId.value = annotation.id;
  addMode.value = false;
}

async function getCurrentPageImageBlob(options: { scale?: number } = {}) {
  const canvas = captureCanvas(options);
  const blob = await new Promise<Blob | null>(resolve => {
    canvas.toBlob(resolve, 'image/png');
  });
  if (!blob) throw new Error(PDF_CAPTURE_UNAVAILABLE);
  return blob;
}

function getCurrentPageImageData() {
  const canvas = captureCanvas();
  const context = canvas.getContext('2d');
  if (!context) return null;
  return context.getImageData(0, 0, canvas.width, canvas.height);
}

function captureCanvas(options: { scale?: number } = {}) {
  const source = stageRef.value?.querySelector('canvas');
  if (!source) throw new Error(PDF_CAPTURE_UNAVAILABLE);
  const sourceContext = source.getContext('2d');
  if (!sourceContext) throw new Error(PDF_CAPTURE_UNAVAILABLE);

  const longest = Math.max(source.width, source.height, 1);
  const targetLongest = options.scale
    ? Math.min(2048, Math.max(1600, longest * options.scale))
    : Math.min(2048, Math.max(1600, longest));
  const ratio = targetLongest / longest;
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(source.width * ratio));
  canvas.height = Math.max(1, Math.round(source.height * ratio));
  const context = canvas.getContext('2d');
  if (!context) throw new Error(PDF_CAPTURE_UNAVAILABLE);
  context.fillStyle = '#fff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function selectAnnotation(annotationId: string) {
  store.selectedAnnotationId.value = annotationId;
}

function updateLeaderPoint(payload: AnnotationPointUpdate) {
  store.updateAnnotation(payload.id, { [payload.point]: payload.value });
}

function setCurrentPage(page: number) {
  if (props.busy) return;
  currentPage.value = Math.min(pageCount.value, Math.max(1, page));
}

function onKeyDown(event: KeyboardEvent) {
  if (event.code !== 'Space' || isEditableTarget(event.target)) return;
  if (activeRuntime.value) event.preventDefault();
  spacePressed.value = true;
}

function onKeyUp(event: KeyboardEvent) {
  if (event.code === 'Space') spacePressed.value = false;
}

function clearKeyboardState() {
  spacePressed.value = false;
}

function isEditableTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element?.closest('input, textarea, [contenteditable="true"]'));
}

function revokeAllObjectUrls() {
  runtimeSources.value.forEach(item => URL.revokeObjectURL(item.objectUrl));
  runtimeSources.value = [];
}

watch(activeSourceId, () => {
  currentPage.value = 1;
  addMode.value = false;
  store.selectedAnnotationId.value = '';
});

watch([activeSourceId, currentPage], ([sourceId, page]) => {
  emit('activeChange', { sourceId, page });
});

onMounted(() => {
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('blur', clearKeyboardState);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown);
  window.removeEventListener('keyup', onKeyUp);
  window.removeEventListener('blur', clearKeyboardState);
  revokeAllObjectUrls();
});

defineExpose({
  getCurrentPageImageBlob,
  getCurrentPageImageData,
  openFilePicker
});
</script>

<template>
  <section class="pdf-workspace">
    <div class="workspace-toolbar">
      <input
        ref="fileInputRef"
        class="hidden-input"
        type="file"
        accept="application/pdf,.pdf"
        multiple
        @change="handleFileSelection"
      />
      <div class="workspace-name">
        <strong>附图画布</strong>
        <span>无引线 PDF</span>
      </div>
      <ElButton type="primary" plain :disabled="busy" @click="openFilePicker">添加附图 PDF</ElButton>
      <ElSelect
        :model-value="activeSourceId"
        class="source-select"
        placeholder="选择当前附图"
        :disabled="!runtimeSources.length || busy"
        @change="selectSource"
      >
        <ElOption v-for="item in runtimeSources" :key="item.sourceId" :label="item.file.name" :value="item.sourceId" />
      </ElSelect>
      <ElButton :disabled="!activeRuntime || busy" @click="removeActiveFile">移除</ElButton>
      <div class="toolbar-divider" />
      <ElPagination
        v-if="activeRuntime"
        size="small"
        background
        layout="prev, pager, next"
        :pager-count="5"
        :current-page="currentPage"
        :page-count="pageCount"
        :disabled="busy"
        @current-change="setCurrentPage"
      />
      <ElButton :type="addMode ? 'primary' : 'default'" :disabled="!activeRuntime || busy" @click="addMode = !addMode">
        {{ addMode ? '点击图面放置引线' : '添加引线' }}
      </ElButton>
      <ElButton :disabled="!activeRuntime" @click="fitStage">适应窗口</ElButton>
      <ElButton :disabled="!activeRuntime" @click="zoomBy(1.15)">放大</ElButton>
      <ElButton :disabled="!activeRuntime" @click="zoomBy(1 / 1.15)">缩小</ElButton>
      <span class="zoom-label">{{ Math.round(zoom * 100) }}%</span>
    </div>

    <div
      ref="viewportRef"
      class="pdf-viewport"
      :class="{ panning, 'space-ready': spacePressed, 'add-mode': addMode }"
      @pointerdown="startPan"
      @pointermove="movePan"
      @pointerup="stopPan"
      @pointercancel="stopPan"
      @wheel.prevent="onWheel"
    >
      <div v-if="!activeRuntime" class="workspace-empty">
        <div class="empty-mark">PDF</div>
        <strong>上传无引线专利附图</strong>
        <span>可一次选择资源 527、528 等多个 PDF；上传后会按顺序自动匹配图号</span>
        <ElButton type="primary" :disabled="busy" @click="openFilePicker">选择附图 PDF</ElButton>
      </div>
      <div v-else ref="stageRef" class="pdf-stage" :style="stageStyle" @pointerdown="onStagePointerDown">
        <VuePdfEmbed
          :key="activeRuntime.sourceId"
          ref="pdfRef"
          class="pdf-document"
          :source="activeRuntime.objectUrl"
          :page="currentPage"
          @rendered="onPdfRendered"
        />
        <LeaderOverlay
          :annotations="currentAnnotations"
          :selected-id="store.selectedAnnotationId.value"
          :stage-width="stageWidth"
          :stage-height="stageHeight"
          @select="selectAnnotation"
          @update="updateLeaderPoint"
        />
      </div>
      <div v-if="activeRuntime" class="interaction-hint">滚轮缩放 · Space + 左键或中键平移</div>
    </div>
  </section>
</template>

<style scoped>
.pdf-workspace {
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

.workspace-name {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  margin-right: 2px;
  color: var(--el-text-color-primary);
  font-size: 12px;
  line-height: 1.25;
}

.workspace-name span {
  color: var(--el-text-color-secondary);
  font-size: 10px;
  font-weight: 400;
}

.hidden-input {
  display: none;
}

.source-select {
  width: 220px;
  flex: 0 0 auto;
}

.toolbar-divider {
  width: 1px;
  height: 24px;
  flex: 0 0 auto;
  background: var(--el-border-color-light);
}

.zoom-label {
  min-width: 42px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.pdf-viewport {
  position: relative;
  display: grid;
  min-height: 0;
  flex: 1;
  place-items: center;
  overflow: hidden;
  background-color: var(--el-fill-color-light);
  background-image:
    linear-gradient(45deg, var(--el-border-color-lighter) 25%, transparent 25%),
    linear-gradient(-45deg, var(--el-border-color-lighter) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--el-border-color-lighter) 75%),
    linear-gradient(-45deg, transparent 75%, var(--el-border-color-lighter) 75%);
  background-position:
    0 0,
    0 8px,
    8px -8px,
    -8px 0;
  background-size: 16px 16px;
}

.pdf-viewport.space-ready {
  cursor: grab;
}

.pdf-viewport.panning {
  cursor: grabbing;
}

.pdf-viewport.add-mode {
  cursor: crosshair;
}

.workspace-empty {
  display: flex;
  max-width: 440px;
  align-items: center;
  flex-direction: column;
  gap: 10px;
  padding: 28px;
  color: var(--el-text-color-primary);
  text-align: center;
}

.workspace-empty span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.empty-mark {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 14px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.pdf-stage {
  position: absolute;
  left: 0;
  top: 0;
  overflow: hidden;
  background: #fff;
  box-shadow: var(--el-box-shadow-light);
  transform-origin: 0 0;
}

.pdf-document {
  display: block;
  width: max-content;
  min-width: 1px;
  min-height: 1px;
}

.pdf-document :deep(canvas) {
  display: block;
}

.interaction-hint {
  position: absolute;
  right: 12px;
  bottom: 10px;
  z-index: 3;
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  padding: 4px 8px;
  background: color-mix(in srgb, var(--el-bg-color) 90%, transparent);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  pointer-events: none;
}
</style>
