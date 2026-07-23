<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessageBox } from 'element-plus';
import {
  createCadSpecTask,
  extractCadSpecTask,
  fetchCadSpecExtraction,
  fetchCadSpecExtractionStatus,
  fetchCadSpecFacts,
  fetchCadSpecLayoutStatus,
  fetchCadSpecRegions,
  fetchCadSpecTasks,
  getCadSpecDrawingImageUrl,
  startCadSpecLayout
} from '@/service/api';

type Box = {
  id: string;
  label: string;
  bbox: number[];
  precision?: string | null;
  kind: 'region' | 'fact';
};

const route = useRoute();
const router = useRouter();

const revisionId = computed(() => String(route.query.revision_id || ''));
const requestedTaskId = computed(() => String(route.query.task_id || ''));
const buildId = computed(() => String(route.query.build_id || ''));
const drawingFile = ref<File | null>(null);
const targetCode = ref('XMS06');
const targetDn = ref('80');
const taskId = ref('');
const taskOptions = ref<Api.CadSpec.TaskSummary[]>([]);
const layoutStatus = ref<Api.CadSpec.LayoutStatus | null>(null);
const extractionStatus = ref<Api.CadSpec.ExtractionStatus | null>(null);
const extractionResult = ref<Api.CadSpec.ExtractionResult | null>(null);
const facts = ref<Api.CadSpec.Fact[]>([]);
const regions = ref<Api.CadSpec.Region[]>([]);
const selectedFact = ref<Api.CadSpec.Fact | null>(null);
const imageSrc = ref('');
const imageWidth = ref(0);
const imageHeight = ref(0);
const zoom = ref(1);
const panX = ref(0);
const panY = ref(0);
const dragging = ref(false);
const dragStart = ref({ x: 0, y: 0, panX: 0, panY: 0 });
const busy = ref(false);
const statusMessage = ref('等待上传二维参数图');
const errorMessage = ref('');
const viewportRef = ref<HTMLElement | null>(null);
const pollTimer = ref<number | null>(null);

const productFacts = computed(() =>
  facts.value.filter(item => item.fact_type === 'product_info' || item.fact_type === 'pressure_class')
);
const dimensionFacts = computed(() => facts.value.filter(item => item.fact_type === 'dimension'));
const rawJson = computed(() => (extractionResult.value ? JSON.stringify(extractionResult.value, null, 2) : ''));
const selectedBox = computed<Box | null>(() => {
  if (!selectedFact.value?.source_bbox_original?.length) return null;
  return {
    id: selectedFact.value.fact_key,
    label: selectedFact.value.fact_key,
    bbox: selectedFact.value.source_bbox_original,
    precision: selectedFact.value.source_bbox_precision,
    kind: 'fact'
  };
});
const regionBoxes = computed<Box[]>(() =>
  regions.value
    .filter(item => item.padded_bbox_pixels?.length === 4)
    .map(item => ({
      id: item.id,
      label: item.region_type,
      bbox: item.padded_bbox_pixels,
      precision: 'region',
      kind: 'region'
    }))
);
const visibleBoxes = computed(() => (selectedBox.value ? [selectedBox.value] : regionBoxes.value));
const selectedFactTitle = computed(() => {
  if (!selectedFact.value) return '未选择字段';
  const value = formatValue(selectedFact.value.normalized_value);
  return `${selectedFact.value.fact_key} = ${value}${selectedFact.value.unit ? ` ${selectedFact.value.unit}` : ''}`;
});
const canSubmit = computed(() => Boolean(revisionId.value && drawingFile.value && !busy.value));
const canReextract = computed(() =>
  Boolean(taskId.value && !busy.value && layoutStatus.value?.status === 'layout_ready')
);
const canQuery = computed(() => Boolean(taskId.value && !busy.value));
const primaryActionLabel = computed(() => (taskId.value ? '重新抽取' : '创建任务'));
const canRunPrimaryAction = computed(() => (taskId.value ? canReextract.value : canSubmit.value));

const taskSelectOptions = computed(() => [
  { task_id: '', file_name: '当前 revision', status: 'created' as Api.CadSpec.LayoutStatusValue },
  ...taskOptions.value
]);

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  drawingFile.value = input.files?.[0] ?? null;
}

async function createTaskAndExtract() {
  if (!revisionId.value) {
    window.$message?.error('缺少 revision_id，请从 CAD 页面进入组件规范');
    return;
  }
  if (!drawingFile.value) {
    window.$message?.error('请先上传二维参数图');
    return;
  }

  resetExtractionState();
  busy.value = true;
  errorMessage.value = '';
  try {
    statusMessage.value = '正在创建任务';
    const created = await createCadSpecTask({
      revision_id: revisionId.value,
      drawing_file: drawingFile.value,
      target_code: normalizedTargetCode(),
      target_dn: targetDn.value
    });
    if (created.error || !created.data) throw new Error('创建任务失败');
    taskId.value = created.data.task_id;
    imageSrc.value = imageUrl('original');
    await loadTaskOptions();

    statusMessage.value = '正在检测版面';
    const layoutStarted = await startCadSpecLayout(taskId.value);
    if (layoutStarted.error) throw new Error('启动版面检测失败');
    await waitForLayoutReady();
    await loadRegions();
    imageSrc.value = imageUrl('inference');
    await nextTick();

    await runExtraction(false);
    await loadTaskOptions();
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}

async function reextract() {
  if (!taskId.value) return;
  try {
    await ElMessageBox.confirm('这会重新调用视觉模型并替换当前 Drawing Facts。', '确认重新抽取', {
      confirmButtonText: '重新抽取',
      cancelButtonText: '取消',
      type: 'warning'
    });
  } catch {
    return;
  }
  busy.value = true;
  errorMessage.value = '';
  selectedFact.value = null;
  extractionResult.value = null;
  facts.value = [];
  try {
    await runExtraction(true);
    await loadTaskOptions();
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}

async function runPrimaryAction() {
  if (taskId.value) {
    await reextract();
    return;
  }
  await createTaskAndExtract();
}

async function queryExtractionResult() {
  if (!taskId.value) return;
  busy.value = true;
  errorMessage.value = '';
  try {
    statusMessage.value = '正在查询已入库抽取结果';
    const statusResult = await fetchCadSpecExtractionStatus(taskId.value);
    if (statusResult.error || !statusResult.data) throw new Error('查询抽取状态失败');
    extractionStatus.value = statusResult.data;
    if (statusResult.data.status === 'failed') throw new Error(errorText(statusResult.data));
    if (statusResult.data.status !== 'review_ready') {
      statusMessage.value = '抽取尚未完成，继续等待结果';
      await waitForExtractionReady();
    }
    await loadExtraction();
    statusMessage.value = '已查询到抽取结果';
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}

async function loadTaskOptions() {
  if (!revisionId.value) return;
  const result = await fetchCadSpecTasks({ revision_id: revisionId.value });
  if (result.error || !result.data) return;
  taskOptions.value = result.data.items;

  if (requestedTaskId.value && requestedTaskId.value !== taskId.value) {
    const requestedTask = taskOptions.value.find(item => item.task_id === requestedTaskId.value);
    if (requestedTask) await selectTask(requestedTask.task_id);
  }
}

async function selectTask(nextTaskId: string) {
  if (!nextTaskId) {
    resetExtractionState();
    await loadTaskOptions();
    return;
  }
  resetTaskData();
  taskId.value = nextTaskId;
  busy.value = true;
  errorMessage.value = '';
  try {
    const [layout, extraction] = await Promise.all([
      fetchCadSpecLayoutStatus(taskId.value),
      fetchCadSpecExtractionStatus(taskId.value)
    ]);
    if (!layout.error && layout.data) layoutStatus.value = layout.data;
    if (!extraction.error && extraction.data) extractionStatus.value = extraction.data;
    await loadRegions();
    imageSrc.value = imageUrl(layoutStatus.value?.status === 'layout_ready' ? 'inference' : 'original');
    if (extractionStatus.value?.status === 'review_ready') await loadExtraction();
    statusMessage.value = extractionStatus.value
      ? `已切换任务：${statusText(extractionStatus.value.status)}`
      : '已切换任务';
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}

async function runExtraction(force: boolean) {
  statusMessage.value = force ? '正在重新抽取整张图' : '正在抽取整张图 Drawing Facts';
  extractionStatus.value = {
    task_id: taskId.value,
    status: 'extracting_product_info',
    progress: 15,
    status_message: 'extracting_product_info'
  };
  const extracted = await extractCadSpecTask(taskId.value, { force });
  if (extracted.error) throw new Error('抽取失败');
  await waitForExtractionReady();
  await loadExtraction();
  statusMessage.value = '抽取完成，等待审核';
}

async function waitForLayoutReady(attempt = 0, readFailures = 0): Promise<void> {
  if (attempt >= 90) throw new Error('版面检测超时，请稍后重试');
  const result = await fetchCadSpecLayoutStatus(taskId.value);
  if (result.error || !result.data) {
    if (readFailures >= 15) throw new Error('读取版面状态失败，请确认后端服务仍在运行');
    statusMessage.value = '读取版面状态超时，后台任务仍在运行，继续等待';
    await delay(1500);
    return waitForLayoutReady(attempt + 1, readFailures + 1);
  }
  layoutStatus.value = result.data;
  statusMessage.value = statusText(result.data.status);
  if (result.data.status === 'layout_ready') return undefined;
  if (result.data.status === 'needs_manual_layout') throw new Error('需要人工修正版面区域后再抽取');
  if (result.data.status === 'failed') throw new Error(errorText(result.data));
  await delay(1200);
  return waitForLayoutReady(attempt + 1, 0);
}

async function waitForExtractionReady(attempt = 0, readFailures = 0): Promise<void> {
  if (attempt >= 500) throw new Error('抽取超时，请稍后查看任务状态');
  const result = await fetchCadSpecExtractionStatus(taskId.value);
  if (result.error || !result.data) {
    if (readFailures >= 60) throw new Error('读取抽取状态失败，请确认后端服务仍在运行');
    statusMessage.value = '读取抽取状态超时，模型仍在处理，继续等待';
    await delay(2000);
    return waitForExtractionReady(attempt + 1, readFailures + 1);
  }
  extractionStatus.value = result.data;
  statusMessage.value = statusText(result.data.status);
  if (result.data.status === 'review_ready') return undefined;
  if (result.data.status === 'failed') throw new Error(errorText(result.data));
  await delay(1200);
  return waitForExtractionReady(attempt + 1, 0);
}

async function loadRegions() {
  if (!taskId.value) return;
  const result = await fetchCadSpecRegions(taskId.value);
  if (!result.error && result.data) regions.value = result.data.items;
}

async function loadExtraction(attempt = 0): Promise<void> {
  const [statusResult, extractionResultData, factResult] = await Promise.all([
    fetchCadSpecExtractionStatus(taskId.value),
    fetchCadSpecExtraction(taskId.value),
    fetchCadSpecFacts(taskId.value, {
      target_code: normalizedTargetCode(),
      target_dn: normalizedTargetDn(),
      page: 1,
      page_size: 200
    })
  ]);
  if (!statusResult.error && statusResult.data) extractionStatus.value = statusResult.data;
  if (extractionResultData.error || !extractionResultData.data) {
    if (attempt >= 20) throw new Error('读取抽取结果失败');
    statusMessage.value = '抽取完成，正在读取结果';
    await delay(1500);
    return loadExtraction(attempt + 1);
  }
  extractionResult.value = extractionResultData.data;
  facts.value = factResult.error || !factResult.data ? extractionResultData.data.facts : factResult.data.items;
  selectedFact.value =
    facts.value.find(item => item.symbol === 'D' || item.fact_key === 'dimension.D') ?? facts.value[0] ?? null;
  return undefined;
}

function resetExtractionState() {
  stopPolling();
  taskId.value = '';
  resetTaskData();
}

function resetTaskData() {
  layoutStatus.value = null;
  extractionStatus.value = null;
  extractionResult.value = null;
  facts.value = [];
  regions.value = [];
  selectedFact.value = null;
  imageSrc.value = '';
  imageWidth.value = 0;
  imageHeight.value = 0;
  zoom.value = 1;
  panX.value = 0;
  panY.value = 0;
}

function selectFact(fact: Api.CadSpec.Fact) {
  selectedFact.value = fact;
}

function editFactValue(fact: Api.CadSpec.Fact) {
  ElMessageBox.prompt('修改显示值', '编辑字段', {
    confirmButtonText: '保存',
    cancelButtonText: '取消',
    inputValue: formatValue(fact.normalized_value)
  })
    .then(({ value }) => {
      const nextValue = value ?? '';
      fact.raw_value = nextValue;
      fact.normalized_value = normalizeEditedValue(nextValue);
      fact.needs_review = true;
      if (selectedFact.value?.fact_key === fact.fact_key) selectedFact.value = fact;
    })
    .catch(() => {});
}

function imageUrl(variant: 'original' | 'inference') {
  return `${getCadSpecDrawingImageUrl(taskId.value, variant)}&t=${Date.now()}`;
}

function onImageLoad(event: Event) {
  const image = event.target as HTMLImageElement;
  imageWidth.value = image.naturalWidth;
  imageHeight.value = image.naturalHeight;
  fitImage();
}

function fitImage() {
  const viewport = viewportRef.value;
  if (!viewport || !imageWidth.value || !imageHeight.value) return;
  const scaleX = (viewport.clientWidth - 32) / imageWidth.value;
  const scaleY = (viewport.clientHeight - 32) / imageHeight.value;
  zoom.value = Math.max(0.1, Math.min(scaleX, scaleY));
  panX.value = Math.max(16, (viewport.clientWidth - imageWidth.value * zoom.value) / 2);
  panY.value = Math.max(16, (viewport.clientHeight - imageHeight.value * zoom.value) / 2);
}

function zoomBy(delta: number) {
  zoom.value = Math.max(0.1, Math.min(6, zoom.value + delta));
}

function onWheel(event: WheelEvent) {
  zoomBy(event.deltaY > 0 ? -0.08 : 0.08);
}

function startDrag(event: MouseEvent) {
  if (!imageSrc.value) return;
  dragging.value = true;
  dragStart.value = { x: event.clientX, y: event.clientY, panX: panX.value, panY: panY.value };
}

function onDrag(event: MouseEvent) {
  if (!dragging.value) return;
  panX.value = dragStart.value.panX + event.clientX - dragStart.value.x;
  panY.value = dragStart.value.panY + event.clientY - dragStart.value.y;
}

function stopDrag() {
  dragging.value = false;
}

function boxStyle(box: Box) {
  const [x1, y1, x2, y2] = box.bbox;
  return {
    left: `${x1}px`,
    top: `${y1}px`,
    width: `${Math.max(1, x2 - x1)}px`,
    height: `${Math.max(1, y2 - y1)}px`
  };
}

function stageStyle() {
  return {
    width: `${imageWidth.value}px`,
    height: `${imageHeight.value}px`,
    transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`
  };
}

function normalizedTargetCode() {
  const value = targetCode.value.trim();
  return value || undefined;
}

function normalizedTargetDn() {
  const value = Number(targetDn.value.trim().toUpperCase().replace(/^DN/, ''));
  return Number.isFinite(value) ? value : null;
}

function statusText(status: string | undefined | null) {
  const labels: Record<string, string> = {
    created: '已创建',
    preprocessing_image: '正在预处理图片',
    detecting_layout: '正在识别版面',
    cropping_regions: '正在生成裁剪图',
    layout_ready: '版面已就绪',
    needs_manual_layout: '需要人工修正版面',
    extracting_product_info: '正在抽取产品信息',
    extracting_table: '正在抽取参数表',
    extracting_symbols: '正在抽取尺寸符号',
    selecting_target_row: '正在选择目标规格行',
    validating_result: '正在校验结果',
    review_ready: '待审核',
    failed: '失败'
  };
  return status ? (labels[status] ?? status) : '未开始';
}

function errorText(status: { error_message?: string | null; error_code?: string | null }) {
  if (status.error_message) return status.error_message;
  if (status.error_code) return `任务失败：${status.error_code}`;
  return '任务失败';
}

function confidenceText(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return `${Math.round(value * 100)}%`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'number') return Number(value).toString();
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function normalizeEditedValue(value: string) {
  const trimmed = value.trim();
  if (trimmed === '') return '';
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : trimmed;
}

function handleError(error: unknown) {
  const message = error instanceof Error ? error.message : '操作失败';
  errorMessage.value = message;
  statusMessage.value = message;
  window.$message?.error(message);
}

function delay(ms: number) {
  return new Promise(resolve => {
    pollTimer.value = window.setTimeout(resolve, ms);
  });
}

function stopPolling() {
  if (pollTimer.value) {
    window.clearTimeout(pollTimer.value);
    pollTimer.value = null;
  }
}

function goBackToCad() {
  if (buildId.value) {
    router.push({ path: '/component-build', query: { build_id: buildId.value } });
    return;
  }
  router.push({ path: '/cad-model' });
}

onBeforeUnmount(() => {
  stopPolling();
});

onMounted(() => {
  loadTaskOptions();
});
</script>

<template>
  <div class="cad-spec-page">
    <header class="spec-toolbar">
      <div class="task-left">
        <div class="title-block">
          <div class="page-title">组件规范</div>
          <ElSelect v-model="taskId" class="task-select" filterable placeholder="选择抽取任务" @change="selectTask">
            <ElOption
              v-for="task in taskSelectOptions"
              :key="task.task_id || 'revision'"
              :label="
                task.task_id
                  ? `${task.file_name || '未命名'} · ${statusText(task.status)}`
                  : `revision_id: ${revisionId || '未传入'}`
              "
              :value="task.task_id"
            />
          </ElSelect>
        </div>

        <label class="file-picker">
          <input accept=".png,.jpg,.jpeg,.webp" type="file" @change="onFileChange" />
          <span>{{ drawingFile?.name || '选择二维参数图' }}</span>
        </label>

        <ElButton
          type="primary"
          :disabled="!canRunPrimaryAction"
          :loading="busy && !canQuery"
          @click="runPrimaryAction"
        >
          {{ primaryActionLabel }}
        </ElButton>
      </div>

      <div class="task-controls">
        <ElInput v-model="targetCode" class="target-input" placeholder="target_code" />
        <ElInput v-model="targetDn" class="target-input small" placeholder="target_dn" />
        <ElButton :disabled="!canQuery" :loading="busy && Boolean(taskId)" @click="queryExtractionResult">
          查询结果
        </ElButton>
        <ElButton text @click="goBackToCad">{{ buildId ? '返回图元建库' : '返回 CAD 页面' }}</ElButton>
      </div>
    </header>

    <div class="status-strip" :class="{ error: Boolean(errorMessage) }">
      <span>{{ statusMessage }}</span>
      <span v-if="layoutStatus">版面：{{ statusText(layoutStatus.status) }}</span>
      <span v-if="extractionStatus">抽取：{{ statusText(extractionStatus.status) }}</span>
      <span v-if="taskId">task_id: {{ taskId }}</span>
    </div>

    <main class="spec-shell">
      <section class="preview-panel">
        <div class="preview-actions">
          <ElButton size="small" @click="fitImage">适应窗口</ElButton>
          <ElButton size="small" @click="zoomBy(0.15)">放大</ElButton>
          <ElButton size="small" @click="zoomBy(-0.15)">缩小</ElButton>
          <span class="zoom-label">{{ Math.round(zoom * 100) }}%</span>
          <span v-if="selectedFact" class="selected-label">{{ selectedFactTitle }}</span>
        </div>

        <div
          ref="viewportRef"
          class="image-viewport"
          :class="{ dragging }"
          @mousedown="startDrag"
          @mousemove="onDrag"
          @mouseup="stopDrag"
          @mouseleave="stopDrag"
          @wheel.prevent="onWheel"
        >
          <ElEmpty v-if="!imageSrc" description="上传参数图后显示预览" />
          <div v-else class="image-stage" :style="stageStyle()">
            <img class="drawing-image" :src="imageSrc" alt="drawing preview" draggable="false" @load="onImageLoad" />
            <div class="bbox-layer">
              <div
                v-for="box in visibleBoxes"
                :key="`${box.kind}-${box.id}`"
                class="bbox"
                :class="{ selected: box.kind === 'fact' }"
                :style="boxStyle(box)"
              >
                <span>{{ box.label }}{{ box.precision ? ` (${box.precision})` : '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <aside class="facts-panel">
        <ElTabs>
          <ElTabPane label="产品信息">
            <ElEmpty v-if="!productFacts.length" description="暂无产品信息" :image-size="46" />
            <button
              v-for="fact in productFacts"
              :key="fact.fact_key"
              class="fact-row"
              :class="{ selected: selectedFact?.fact_key === fact.fact_key }"
              type="button"
              @click="selectFact(fact)"
              @dblclick="editFactValue(fact)"
            >
              <span class="fact-key">{{ fact.fact_key }}</span>
              <span class="fact-value">{{ formatValue(fact.normalized_value) }}</span>
              <span class="fact-meta">
                {{ confidenceText(fact.confidence) }} · {{ fact.source_bbox_precision || '-' }}
              </span>
            </button>
          </ElTabPane>

          <ElTabPane label="目标参数行">
            <div class="target-summary">
              <div>目标代码：{{ normalizedTargetCode() || '-' }}</div>
              <div>目标 DN：{{ normalizedTargetDn() || '-' }}</div>
              <div>查询状态：{{ dimensionFacts.length ? '已匹配' : '-' }}</div>
            </div>
            <ElEmpty v-if="!dimensionFacts.length" description="暂无目标参数" :image-size="46" />
            <button
              v-for="fact in dimensionFacts"
              :key="fact.fact_key"
              class="fact-row"
              :class="{ selected: selectedFact?.fact_key === fact.fact_key }"
              type="button"
              @click="selectFact(fact)"
              @dblclick="editFactValue(fact)"
            >
              <span class="fact-key">{{ fact.symbol || fact.fact_key }}</span>
              <span class="fact-value">
                {{ formatValue(fact.normalized_value) }}{{ fact.unit ? ` ${fact.unit}` : '' }}
              </span>
              <span class="fact-meta">{{ fact.operator }} · {{ fact.source_bbox_precision || '-' }}</span>
            </button>
          </ElTabPane>

          <ElTabPane label="Drawing Facts">
            <ElEmpty v-if="!facts.length" description="暂无 Drawing Facts" :image-size="46" />
            <button
              v-for="fact in facts"
              :key="fact.fact_key"
              class="fact-row"
              :class="{ selected: selectedFact?.fact_key === fact.fact_key }"
              type="button"
              @click="selectFact(fact)"
              @dblclick="editFactValue(fact)"
            >
              <span class="fact-key">{{ fact.fact_key }}</span>
              <span class="fact-value">{{ formatValue(fact.raw_value) }}</span>
              <span class="fact-meta">{{ fact.operator }} · {{ confidenceText(fact.confidence) }}</span>
            </button>
          </ElTabPane>

          <ElTabPane label="原始 VLM JSON">
            <ElInput
              :model-value="rawJson"
              :rows="22"
              class="json-viewer"
              readonly
              resize="none"
              type="textarea"
              placeholder="抽取完成后显示原始结构化 JSON"
            />
          </ElTabPane>
        </ElTabs>

        <section class="selected-detail">
          <div class="detail-title">字段证据</div>
          <dl>
            <dt>字段</dt>
            <dd>{{ selectedFact?.fact_key || '-' }}</dd>
            <dt>原始值</dt>
            <dd>{{ formatValue(selectedFact?.raw_value) }}</dd>
            <dt>归一化值</dt>
            <dd>{{ formatValue(selectedFact?.normalized_value) }}</dd>
            <dt>证据精度</dt>
            <dd>{{ selectedFact?.source_bbox_precision || '-' }}</dd>
            <dt>bbox</dt>
            <dd>{{ selectedFact?.source_bbox_original?.join(', ') || '-' }}</dd>
          </dl>
        </section>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.cad-spec-page {
  display: flex;
  height: calc(100vh - 118px);
  min-height: 680px;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.spec-toolbar,
.status-strip,
.preview-panel,
.facts-panel {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.spec-toolbar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
}

.task-left {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 8px;
}

.title-block {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.page-title {
  flex: 0 0 auto;
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 700;
}

.task-select {
  width: 300px;
}

.task-controls {
  display: flex;
  min-width: 0;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-left: auto;
}

.file-picker {
  display: inline-flex;
  max-width: 260px;
  height: 32px;
  align-items: center;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  padding: 0 10px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 13px;
}

.file-picker input {
  display: none;
}

.file-picker span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.target-input {
  width: 150px;
}

.target-input.small {
  width: 96px;
}

.status-strip {
  display: flex;
  min-height: 34px;
  flex: 0 0 auto;
  align-items: center;
  gap: 18px;
  padding: 7px 12px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.status-strip.error {
  border-color: var(--el-color-danger-light-5);
  color: var(--el-color-danger);
}

.spec-shell {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(520px, 1fr) 430px;
  gap: 10px;
}

.preview-panel,
.facts-panel {
  min-width: 0;
  min-height: 0;
}

.preview-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 8px 10px;
}

.zoom-label,
.selected-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.selected-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-viewport {
  position: relative;
  min-height: 0;
  flex: 1;
  overflow: hidden;
  background:
    linear-gradient(45deg, var(--el-fill-color-light) 25%, transparent 25%),
    linear-gradient(-45deg, var(--el-fill-color-light) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--el-fill-color-light) 75%),
    linear-gradient(-45deg, transparent 75%, var(--el-fill-color-light) 75%);
  background-position:
    0 0,
    0 8px,
    8px -8px,
    -8px 0;
  background-size: 16px 16px;
  cursor: grab;
}

.image-viewport.dragging {
  cursor: grabbing;
}

.image-stage {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
}

.drawing-image {
  display: block;
  width: 100%;
  height: 100%;
  user-select: none;
}

.bbox-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bbox {
  position: absolute;
  border: 2px solid var(--el-color-warning);
  background: rgba(230, 162, 60, 0.12);
  color: var(--el-color-warning);
}

.bbox.selected {
  border-color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.18);
  color: var(--el-color-primary);
}

.bbox span {
  position: absolute;
  left: 0;
  top: -22px;
  max-width: 280px;
  overflow: hidden;
  border-radius: 4px;
  background: var(--el-bg-color);
  padding: 2px 6px;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facts-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 10px;
}

.facts-panel :deep(.el-tabs) {
  min-height: 0;
  flex: 1;
}

.facts-panel :deep(.el-tabs__content) {
  height: calc(100% - 50px);
  overflow: auto;
}

.fact-row {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(110px, 1fr) minmax(86px, auto);
  gap: 4px 8px;
  border: 0;
  border-radius: 6px;
  margin-bottom: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 8px;
  text-align: left;
}

.fact-row:hover,
.fact-row.selected {
  background: var(--el-color-primary-light-9);
}

.fact-key {
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fact-value {
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}

.fact-meta {
  grid-column: 1 / -1;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.target-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 10px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.json-viewer :deep(textarea) {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
}

.selected-detail {
  flex: 0 0 auto;
  border-top: 1px solid var(--el-border-color-light);
  margin-top: 10px;
  padding-top: 10px;
}

.detail-title {
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 700;
}

.selected-detail dl {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr);
  gap: 6px 8px;
  margin: 0;
  font-size: 12px;
}

.selected-detail dt {
  color: var(--el-text-color-secondary);
}

.selected-detail dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

@media (max-width: 1100px) {
  .cad-spec-page {
    height: auto;
    overflow: visible;
  }

  .spec-toolbar,
  .task-left,
  .task-controls {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .task-controls {
    margin-left: 0;
  }

  .spec-shell {
    display: flex;
    flex-direction: column;
  }

  .preview-panel {
    min-height: 520px;
  }

  .facts-panel {
    min-height: 520px;
  }
}
</style>
