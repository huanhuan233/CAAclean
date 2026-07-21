<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { UploadRequestOptions } from 'element-plus';
import {
  fetchCadEdgeTopology,
  fetchCadEntities,
  fetchCadEntity,
  fetchCadFaceTopology,
  fetchCadMeshes,
  fetchCadModels,
  fetchCadRevisionStatus,
  fetchCadStructureTree,
  uploadCadModel
} from '@/service/api';
import CadViewer from './modules/CadViewer.vue';

type GeometryTab = 'face' | 'edge' | 'vertex';

const loadingModels = ref(false);
const loadingTree = ref(false);
const loadingMeshes = ref(false);
const loadingEntities = ref(false);
const uploading = ref(false);

const models = ref<Api.Cad.ModelSummary[]>([]);
const selectedModelId = ref('');
const selectedRevisionId = ref('');
const status = ref<Api.Cad.ParseStatus | null>(null);
const treeData = ref<Api.Cad.TreeNode[]>([]);
const viewerMeshes = ref<Api.Cad.Mesh[]>([]);
const selectedNode = ref<Api.Cad.TreeNode | null>(null);
const selectedEntity = ref<Api.Cad.Entity | null>(null);
const selectedFaceId = ref('');
const solidFaceIds = ref<string[]>([]);
const faceTopology = ref<Api.Cad.FaceTopology | null>(null);
const edgeTopology = ref<Api.Cad.EdgeTopology | null>(null);
const pollTimer = ref<number | null>(null);
const entityCache = ref(new Map<string, Api.Cad.Entity>());

const activeGeometryTab = ref<GeometryTab>('face');
const geometryKeyword = ref('');
const geometryTypeFilter = ref('');
const geometryPage = ref(1);
const geometryPageSize = ref(20);
const geometryRows = ref<Api.Cad.Entity[]>([]);
const geometryTotal = ref(0);

const selectedModel = computed(() => models.value.find(item => item.id === selectedModelId.value) ?? null);
const isProcessing = computed(() => status.value?.status === 'queued' || status.value?.status === 'processing');
const progress = computed(() => status.value?.progress ?? selectedModel.value?.progress ?? 0);
const statusText = computed(() => {
  if (status.value?.status === 'completed' || selectedModel.value?.status === 'completed') return '解析完成';
  if (status.value?.status === 'failed') return '解析失败';
  if (status.value?.status === 'processing') return '解析中';
  if (status.value?.status === 'queued') return '排队中';
  return '未选择';
});

const faceCount = computed(() => selectedModel.value?.face_count ?? 0);
const edgeCount = computed(() => selectedModel.value?.edge_count ?? 0);
const vertexCount = computed(() => selectedModel.value?.vertex_count ?? 0);

function stopPolling() {
  if (pollTimer.value) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

function cacheEntities(items: Api.Cad.Entity[]) {
  const next = new Map(entityCache.value);
  items.forEach(item => next.set(item.id, item));
  entityCache.value = next;
}

async function loadModels() {
  loadingModels.value = true;
  try {
    const result = await fetchCadModels({ page: 1, page_size: 50 });
    if (result.error || !result.data) return;
    models.value = result.data.items;
    if (!selectedModelId.value && result.data.items.length > 0) {
      await selectModel(result.data.items[0]);
    }
  } finally {
    loadingModels.value = false;
  }
}

async function loadStatus(revisionId = selectedRevisionId.value) {
  if (!revisionId) return;
  const result = await fetchCadRevisionStatus(revisionId);
  if (result.error || !result.data) return;
  status.value = result.data;
  if (result.data.status === 'completed') {
    stopPolling();
    await Promise.all([loadStructureTree(revisionId), loadViewerMeshes(revisionId), loadGeometryObjects()]);
    await loadModels();
  }
  if (result.data.status === 'failed') stopPolling();
}

async function loadStructureTree(revisionId = selectedRevisionId.value) {
  if (!revisionId) return;
  loadingTree.value = true;
  try {
    const result = await fetchCadStructureTree(revisionId);
    if (result.error || !result.data) return;
    treeData.value = result.data;
  } finally {
    loadingTree.value = false;
  }
}

async function loadViewerMeshes(revisionId = selectedRevisionId.value) {
  if (!revisionId) return;
  loadingMeshes.value = true;
  try {
    const result = await fetchCadMeshes(revisionId, { page: 1, page_size: 5000 });
    if (result.error || !result.data) return;
    viewerMeshes.value = result.data.items;
  } finally {
    loadingMeshes.value = false;
  }
}

async function loadGeometryObjects() {
  if (!selectedRevisionId.value) return;
  loadingEntities.value = true;
  try {
    const result = await fetchCadEntities(selectedRevisionId.value, {
      entity_type: activeGeometryTab.value,
      geometry_type: geometryTypeFilter.value || undefined,
      keyword: geometryKeyword.value || undefined,
      page: geometryPage.value,
      page_size: geometryPageSize.value
    });
    if (result.error || !result.data) return;
    geometryRows.value = result.data.items;
    geometryTotal.value = result.data.total;
    cacheEntities(result.data.items);
  } finally {
    loadingEntities.value = false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer.value = window.setInterval(() => {
    runAsync(loadStatus());
  }, 2000);
}

function resetSelection() {
  selectedNode.value = null;
  selectedEntity.value = null;
  selectedFaceId.value = '';
  solidFaceIds.value = [];
  faceTopology.value = null;
  edgeTopology.value = null;
}

async function selectModel(model: Api.Cad.ModelSummary) {
  stopPolling();
  selectedModelId.value = model.id;
  selectedRevisionId.value = model.current_revision_id ?? '';
  status.value = null;
  treeData.value = [];
  viewerMeshes.value = [];
  geometryRows.value = [];
  geometryTotal.value = 0;
  entityCache.value = new Map();
  resetSelection();
  if (!selectedRevisionId.value) return;
  await loadStatus(selectedRevisionId.value);
  const currentStatus = status.value as Api.Cad.ParseStatus | null;
  if (currentStatus?.status === 'completed') {
    await Promise.all([
      loadStructureTree(selectedRevisionId.value),
      loadViewerMeshes(selectedRevisionId.value),
      loadGeometryObjects()
    ]);
  } else if (isProcessing.value) {
    startPolling();
  }
}

async function handleUpload(options: UploadRequestOptions) {
  const file = options.file;
  uploading.value = true;
  try {
    const result = await uploadCadModel(file, file.name.replace(/\.(step|stp)$/i, ''));
    if (result.error || !result.data) throw new Error('upload failed');
    selectedModelId.value = result.data.model_id;
    selectedRevisionId.value = result.data.revision_id;
    status.value = {
      status: result.data.status,
      progress: 0,
      status_message: 'queued',
      error_code: null,
      error_message: null
    };
    treeData.value = [];
    viewerMeshes.value = [];
    geometryRows.value = [];
    geometryTotal.value = 0;
    resetSelection();
    await loadModels();
    startPolling();
    options.onSuccess(result.data);
  } catch (error) {
    options.onError(error as Parameters<typeof options.onError>[0]);
  } finally {
    uploading.value = false;
  }
}

function beforeUpload(file: File) {
  const ok = /\.(step|stp)$/i.test(file.name);
  if (!ok) window.$message?.error('只支持 STEP/STP 文件');
  return ok;
}

async function handleTreeClick(node: Api.Cad.TreeNode) {
  selectedNode.value = node;
  selectedEntity.value = null;
  selectedFaceId.value = '';
  faceTopology.value = null;
  edgeTopology.value = null;
  solidFaceIds.value = [];

  if (node.entity_type === 'solid' && selectedRevisionId.value) {
    const result = await fetchCadMeshes(selectedRevisionId.value, {
      parent_entity_id: node.id,
      page: 1,
      page_size: 5000
    });
    if (!result.error && result.data) {
      solidFaceIds.value = result.data.items.map(item => item.entity_id);
    }
  }
}

async function selectEntity(entity: Api.Cad.Entity) {
  selectedEntity.value = entity;
  selectedNode.value = null;
  faceTopology.value = null;
  edgeTopology.value = null;
  solidFaceIds.value = [];
  selectedFaceId.value = entity.entity_type === 'face' ? entity.id : '';
  cacheEntities([entity]);

  if (!selectedRevisionId.value) return;
  if (entity.entity_type === 'face') {
    const result = await fetchCadFaceTopology(selectedRevisionId.value, entity.id);
    if (!result.error && result.data) {
      faceTopology.value = result.data;
      cacheEntities([...(result.data.edges ?? []), ...(result.data.adjacent_faces ?? [])]);
    }
  } else if (entity.entity_type === 'edge') {
    const result = await fetchCadEdgeTopology(selectedRevisionId.value, entity.id);
    if (!result.error && result.data) {
      edgeTopology.value = result.data;
      cacheEntities([...(result.data.vertices ?? []), ...(result.data.faces ?? [])]);
    }
  }
}

async function handleViewerFaceClick(entityId: string) {
  const cached = entityCache.value.get(entityId);
  if (cached) {
    await selectEntity(cached);
    return;
  }
  if (!selectedRevisionId.value) return;
  const result = await fetchCadEntity(selectedRevisionId.value, entityId);
  if (!result.error && result.data) await selectEntity(result.data);
}

function applyGeometrySearch() {
  geometryPage.value = 1;
  runAsync(loadGeometryObjects());
}

function nodeLabel(data: Record<string, unknown>) {
  const node = data as unknown as Api.Cad.TreeNode;
  return node.label || node.source_ref || node.entity_type;
}

function displayName(entity: Api.Cad.Entity | Api.Cad.TreeNode | null) {
  if (!entity) return '—';
  if ('name' in entity) return entity.label || entity.name || entity.source_ref || entity.entity_type;
  return entity.label || entity.source_ref || entity.entity_type;
}

function empty(value: unknown) {
  return value === null || value === undefined || value === '' ? '—' : value;
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) return '—';
  return Number(value)
    .toFixed(4)
    .replace(/\.?0+$/, '');
}

function formatObject(value: unknown) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return '—';
  }
}

function summarizeParams(value: unknown) {
  const text = formatObject(value);
  if (text === '—') return text;
  return text.length > 120 ? `${text.slice(0, 120)}...` : text;
}

function formatPoint(value: unknown) {
  if (Array.isArray(value)) return value.map(item => formatNumber(Number(item))).join(', ');
  if (value && typeof value === 'object') {
    const point = value as Record<string, unknown>;
    const values = [point.x, point.y, point.z].filter(item => item !== undefined);
    if (values.length) return values.map(item => formatNumber(Number(item))).join(', ');
  }
  return '—';
}

function vertexCoordinate(entity: Api.Cad.Entity) {
  return formatPoint(entity.geometry?.point ?? entity.center);
}

function entityTypeLabel(type: string) {
  const labels: Record<string, string> = {
    face: '面',
    edge: '边',
    vertex: '顶点',
    solid: '实体'
  };
  return labels[type] ?? type;
}

watch([activeGeometryTab, geometryPage, geometryPageSize], () => {
  runAsync(loadGeometryObjects());
});

onMounted(() => {
  runAsync(loadModels());
});

function runAsync(task: Promise<unknown>) {
  task.catch(() => undefined);
}

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<template>
  <div class="cad-page">
    <div class="cad-toolbar">
      <ElUpload
        :show-file-list="false"
        :http-request="handleUpload"
        :before-upload="beforeUpload"
        :disabled="uploading"
        accept=".step,.stp"
      >
        <ElButton type="primary" :loading="uploading">
          <template #icon>
            <icon-carbon-upload />
          </template>
          上传 STEP
        </ElButton>
      </ElUpload>

      <ElButton :loading="loadingModels" @click="loadModels">
        <template #icon>
          <icon-ic-round-refresh />
        </template>
        刷新
      </ElButton>

      <div class="status-area">
        <ElTag :type="statusText === '解析完成' ? 'success' : statusText === '解析失败' ? 'danger' : 'info'">
          {{ statusText }}
        </ElTag>
        <ElProgress v-if="isProcessing" :percentage="progress" :stroke-width="8" class="status-progress" />
        <div v-else-if="selectedModel" class="status-counts">
          <span>Face {{ faceCount }}</span>
          <span>Edge {{ edgeCount }}</span>
          <span>Vertex {{ vertexCount }}</span>
        </div>
      </div>
    </div>

    <div class="cad-shell">
      <aside class="left-panel">
        <section class="panel-block models-block">
          <div class="panel-title">模型</div>
          <ElScrollbar class="models-scroll">
            <ElEmpty v-if="!models.length && !loadingModels" description="暂无模型" />
            <button
              v-for="model in models"
              :key="model.id"
              class="model-row"
              :class="{ active: model.id === selectedModelId }"
              type="button"
              @click="selectModel(model)"
            >
              <span class="model-name">{{ model.name }}</span>
              <span class="model-meta">{{ model.status ?? 'unknown' }} · Face {{ model.face_count ?? 0 }}</span>
            </button>
          </ElScrollbar>
        </section>

        <section class="panel-block tree-block">
          <div class="panel-title">产品结构</div>
          <ElSkeleton v-if="loadingTree" :rows="7" animated />
          <ElEmpty v-else-if="!treeData.length" description="解析完成后显示结构" />
          <ElTree
            v-else
            :data="treeData"
            node-key="id"
            default-expand-all
            highlight-current
            :props="{ children: 'children', label: nodeLabel }"
            @node-click="handleTreeClick"
          />
        </section>
      </aside>

      <main v-loading="loadingMeshes" class="viewer-panel">
        <CadViewer
          :meshes="viewerMeshes"
          :selected-face-id="selectedFaceId"
          :highlight-face-ids="solidFaceIds"
          @face-click="handleViewerFaceClick"
        />
      </main>

      <aside class="right-panel">
        <div class="panel-title">属性</div>
        <ElDescriptions v-if="selectedEntity" :column="1" border size="small">
          <ElDescriptionsItem label="名称">{{ displayName(selectedEntity) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="UUID">{{ selectedEntity.id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="source_ref">{{ empty(selectedEntity.source_ref) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="geometry_type">{{ empty(selectedEntity.geometry_type) }}</ElDescriptionsItem>
          <ElDescriptionsItem v-if="selectedEntity.entity_type === 'face'" label="area">
            {{ formatNumber(selectedEntity.area) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="selectedEntity.entity_type === 'edge'" label="length">
            {{ formatNumber(selectedEntity.length) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="selectedEntity.entity_type !== 'vertex'" label="center">
            {{ formatPoint(selectedEntity.center) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="selectedEntity.entity_type === 'vertex'" label="坐标">
            {{ vertexCoordinate(selectedEntity) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="selectedEntity.entity_type !== 'vertex'" label="bounding_box">
            <span class="json-line">{{ formatObject(selectedEntity.bounding_box) }}</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="selectedEntity.entity_type !== 'vertex'" label="geometry 参数">
            <span class="json-line">{{ formatObject(selectedEntity.geometry) }}</span>
          </ElDescriptionsItem>
        </ElDescriptions>

        <ElDescriptions v-else-if="selectedNode" :column="1" border size="small">
          <ElDescriptionsItem label="名称">{{ displayName(selectedNode) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="UUID">{{ selectedNode.id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="类型">{{ entityTypeLabel(selectedNode.entity_type) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="source_ref">{{ empty(selectedNode.source_ref) }}</ElDescriptionsItem>
        </ElDescriptions>

        <ElEmpty v-else description="点击结构、面、边或顶点查看属性" />

        <section v-if="selectedEntity?.entity_type === 'face'" class="topology-block">
          <div class="sub-title">关联 Edge</div>
          <ElEmpty v-if="!faceTopology?.edges?.length" description="—" :image-size="36" />
          <div v-else class="relation-list">
            <ElButton v-for="edge in faceTopology.edges" :key="edge.id" link type="primary" @click="selectEntity(edge)">
              {{ displayName(edge) }} · {{ empty(edge.geometry_type) }}
            </ElButton>
          </div>

          <div class="sub-title">相邻 Face</div>
          <ElEmpty v-if="!faceTopology?.adjacent_faces?.length" description="—" :image-size="36" />
          <div v-else class="relation-list">
            <ElButton
              v-for="face in faceTopology.adjacent_faces"
              :key="face.id"
              link
              type="primary"
              @click="selectEntity(face)"
            >
              {{ displayName(face) }}
            </ElButton>
          </div>
        </section>

        <section v-if="selectedEntity?.entity_type === 'edge'" class="topology-block">
          <div class="sub-title">关联 Vertex</div>
          <ElEmpty v-if="!edgeTopology?.vertices?.length" description="—" :image-size="36" />
          <div v-else class="relation-list">
            <ElButton
              v-for="vertex in edgeTopology.vertices"
              :key="vertex.id"
              link
              type="primary"
              @click="selectEntity(vertex)"
            >
              {{ displayName(vertex) }} · {{ vertexCoordinate(vertex) }}
            </ElButton>
          </div>

          <div class="sub-title">所属 Face</div>
          <ElEmpty v-if="!edgeTopology?.faces?.length" description="—" :image-size="36" />
          <div v-else class="relation-list">
            <ElButton v-for="face in edgeTopology.faces" :key="face.id" link type="primary" @click="selectEntity(face)">
              {{ displayName(face) }}
            </ElButton>
          </div>
        </section>
      </aside>
    </div>

    <section class="geometry-panel">
      <div class="geometry-header">
        <ElTabs v-model="activeGeometryTab" class="geometry-tabs">
          <ElTabPane label="面（Face）" name="face" />
          <ElTabPane label="边（Edge）" name="edge" />
          <ElTabPane label="顶点（Vertex）" name="vertex" />
        </ElTabs>
        <div class="geometry-filters">
          <ElInput
            v-model="geometryKeyword"
            clearable
            placeholder="source_ref 搜索"
            @clear="applyGeometrySearch"
            @keyup.enter="applyGeometrySearch"
          />
          <ElInput
            v-model="geometryTypeFilter"
            clearable
            placeholder="geometry_type 筛选"
            @clear="applyGeometrySearch"
            @keyup.enter="applyGeometrySearch"
          />
          <ElButton type="primary" @click="applyGeometrySearch">查询</ElButton>
        </div>
      </div>

      <ElTable
        v-loading="loadingEntities"
        :data="geometryRows"
        height="260"
        stripe
        highlight-current-row
        row-key="id"
        @row-click="selectEntity"
      >
        <ElTableColumn prop="source_ref" label="source_ref" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="geometry_type" label="geometry_type" min-width="140" show-overflow-tooltip />
        <ElTableColumn v-if="activeGeometryTab === 'face'" label="area" width="120">
          <template #default="{ row }">{{ formatNumber(row.area) }}</template>
        </ElTableColumn>
        <ElTableColumn v-if="activeGeometryTab === 'edge'" label="length" width="120">
          <template #default="{ row }">{{ formatNumber(row.length) }}</template>
        </ElTableColumn>
        <ElTableColumn v-if="activeGeometryTab === 'vertex'" label="坐标" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ vertexCoordinate(row) }}</template>
        </ElTableColumn>
        <ElTableColumn v-if="activeGeometryTab !== 'vertex'" label="主要参数摘要" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ summarizeParams(row.geometry) }}</template>
        </ElTableColumn>
      </ElTable>

      <div class="pagination-row">
        <ElPagination
          v-model:current-page="geometryPage"
          v-model:page-size="geometryPageSize"
          :total="geometryTotal"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.cad-page {
  display: flex;
  min-height: calc(100vh - 118px);
  flex-direction: column;
  gap: 12px;
}

.cad-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 8px 0 12px;
}

.status-area {
  display: flex;
  min-width: 280px;
  flex: 1;
  align-items: center;
  gap: 12px;
}

.status-progress {
  max-width: 360px;
  flex: 1;
}

.status-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.cad-shell {
  display: grid;
  min-height: 520px;
  flex: 1;
  grid-template-columns: minmax(230px, 280px) minmax(420px, 1fr) minmax(300px, 380px);
  gap: 12px;
}

.left-panel,
.right-panel,
.geometry-panel {
  min-width: 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.left-panel {
  display: grid;
  min-height: 0;
  grid-template-rows: 210px minmax(0, 1fr);
}

.panel-block,
.right-panel,
.geometry-panel {
  padding: 12px;
}

.models-block {
  border-bottom: 1px solid var(--el-border-color-light);
}

.panel-title {
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 600;
}

.models-scroll {
  height: 162px;
}

.model-row {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  border: 0;
  border-radius: 6px;
  margin-bottom: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 8px;
  text-align: left;
}

.model-row:hover,
.model-row.active {
  background: var(--el-color-primary-light-9);
}

.model-name {
  width: 100%;
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-meta {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.tree-block {
  min-height: 0;
  overflow: hidden;
}

.tree-block :deep(.el-tree-node__label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.viewer-panel {
  min-width: 0;
  min-height: 520px;
}

.right-panel {
  min-height: 0;
  overflow: auto;
}

.json-line {
  display: inline-block;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.topology-block {
  margin-top: 14px;
  border-top: 1px solid var(--el-border-color-light);
  padding-top: 12px;
}

.sub-title {
  margin: 10px 0 6px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 600;
}

.relation-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.geometry-panel {
  padding-bottom: 10px;
}

.geometry-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.geometry-tabs {
  min-width: 330px;
}

.geometry-filters {
  display: grid;
  width: min(100%, 560px);
  grid-template-columns: minmax(140px, 1fr) minmax(140px, 1fr) auto;
  gap: 8px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding-top: 10px;
}

@media (max-width: 1280px) {
  .cad-shell {
    grid-template-columns: minmax(220px, 260px) minmax(360px, 1fr);
  }

  .right-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .cad-shell,
  .geometry-header,
  .geometry-filters {
    display: flex;
    flex-direction: column;
  }

  .left-panel {
    grid-template-rows: auto auto;
  }

  .viewer-panel {
    min-height: 420px;
  }

  .geometry-filters {
    width: 100%;
  }
}
</style>
