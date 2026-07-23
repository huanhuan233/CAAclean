<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import {
  createComponentBuild,
  fetchComponentBuild,
  fetchComponentBuildStatus,
  fetchComponentBuildTree,
  retryComponentBuild
} from '@/service/api';

defineOptions({ name: 'ComponentBuild' });

type ComponentTreeNode = Api.ComponentBuild.TreeNode;
type RawTreeNode = Partial<ComponentTreeNode> & { name?: string; node_type?: string };

const route = useRoute();
const router = useRouter();
const treeRef = ref<{
  filter: (keyword: string) => void;
  getNode: (key: string) => { expand?: () => void } | undefined;
  setCurrentKey: (key?: string) => void;
}>();
const formRef = ref<FormInstance>();

const treeLoading = ref(false);
const refreshing = ref(false);
const submitting = ref(false);
const retrying = ref(false);
const drawerVisible = ref(false);
const searchKeyword = ref('');
const treeData = ref<ComponentTreeNode[]>([]);
const selectedNodeId = ref('');
const selectedBuild = ref<Api.ComponentBuild.BuildDetail | null>(null);
const buildStatuses = ref<Record<string, Api.ComponentBuild.BuildStatus>>({});
const pollTimer = ref<number | null>(null);
const polling = ref(false);
const statusUnavailable = ref(false);
const viewportWidth = ref(window.innerWidth);

const form = ref(createDefaultForm());
const stepFile = ref<File | null>(null);
const drawingFile = ref<File | null>(null);

const formRules: FormRules = {
  component_id: [{ required: true, message: '请输入图元 ID', trigger: 'blur' }],
  component_name: [{ required: true, message: '请输入图元名称', trigger: 'blur' }],
  component_type: [{ required: true, message: '请输入图元类型', trigger: 'blur' }]
};

const selectedNode = computed(() => findNodeById(treeData.value, selectedNodeId.value));
const selectedBuildId = computed(() => {
  if (!selectedNode.value) return '';
  return selectedNode.value.node_type === 'build' ? selectedNode.value.id : selectedNode.value.build_id || '';
});
const selectedBuildStatus = computed(() => buildStatuses.value[selectedBuildId.value] || null);
const isSourceNode = computed(() => {
  const type = selectedNode.value?.node_type;
  return type === 'reference_step' || type === 'drawing';
});
const isFutureNode = computed(() => selectedNode.value?.node_type === 'fusion' || selectedNode.value?.node_type === 'yaml' || selectedNode.value?.node_type === 'future');
const drawerSize = computed(() => (viewportWidth.value < 520 ? '100%' : 440));

const sourceStatus = computed(() => {
  if (!selectedNode.value || !selectedBuildStatus.value) return null;
  return selectedNode.value.node_type === 'reference_step'
    ? selectedBuildStatus.value.sources.reference_step
    : selectedNode.value.node_type === 'drawing'
      ? selectedBuildStatus.value.sources.drawing
      : null;
});

const canViewSource = computed(() => {
  const node = selectedNode.value;
  if (!node?.target) return false;
  return (
    (node.node_type === 'reference_step' && node.status === 'completed' && Boolean(node.target.revision_id)) ||
    (node.node_type === 'drawing' && node.status === 'review_ready' && Boolean(node.target.revision_id && node.target.task_id))
  );
});

const canRetryDrawing = computed(() => selectedNode.value?.node_type === 'drawing' && isFailure(selectedNode.value.status));
const canReuploadStep = computed(() => selectedNode.value?.node_type === 'reference_step' && isFailure(selectedNode.value.status));

function createDefaultForm(): Omit<Api.ComponentBuild.CreatePayload, 'step_file' | 'drawing_file'> {
  return {
    component_id: '',
    component_name: '',
    component_type: '',
    component_subtype: '',
    family: '',
    standard_number: '',
    version: '1.0.0',
    default_dn: undefined,
    default_pn: undefined
  };
}

function normalizeNodeType(nodeType?: string): Api.ComponentBuild.NodeType {
  const aliases: Record<string, Api.ComponentBuild.NodeType> = {
    data_fusion: 'fusion',
    component_spec: 'yaml',
    publish_validation: 'future'
  };
  const supported = new Set<Api.ComponentBuild.NodeType>([
    'root',
    'family',
    'type',
    'subtype',
    'component',
    'build',
    'folder',
    'reference_step',
    'drawing',
    'fusion',
    'yaml',
    'future'
  ]);
  if (nodeType && supported.has(nodeType as Api.ComponentBuild.NodeType)) return nodeType as Api.ComponentBuild.NodeType;
  return aliases[nodeType || ''] || 'future';
}

function normalizeTree(nodes: RawTreeNode[], parentBuildId: string | null = null, parentId = 'tree'): ComponentTreeNode[] {
  return nodes.map((node, index) => {
    const nodeType = normalizeNodeType(node.node_type);
    const buildId = node.build_id || (nodeType === 'build' ? node.id || null : parentBuildId);
    const id = node.id || `${parentId}:${nodeType}:${index}`;
    const children = normalizeTree((node.children || []) as RawTreeNode[], buildId, id);
    return {
      id,
      label: node.label || node.name || futureLabel(nodeType),
      node_type: nodeType,
      status: node.status || (nodeType === 'future' || nodeType === 'fusion' || nodeType === 'yaml' ? 'future' : 'pending'),
      progress: typeof node.progress === 'number' ? node.progress : null,
      disabled: Boolean(node.disabled) || nodeType === 'future' || nodeType === 'fusion' || nodeType === 'yaml',
      build_id: buildId,
      target: node.target || null,
      status_label: node.status_label || null,
      status_message: node.status_message || null,
      error_code: node.error_code || null,
      error_message: node.error_message || null,
      children
    };
  });
}

function findNodeById(nodes: ComponentTreeNode[], id: string): ComponentTreeNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    const found = findNodeById(node.children, id);
    if (found) return found;
  }
  return null;
}

function allBuildNodes(nodes: ComponentTreeNode[]): ComponentTreeNode[] {
  return nodes.flatMap(node => [node, ...allBuildNodes(node.children)]).filter(node => node.node_type === 'build');
}

function hasPendingBuilds() {
  return allBuildNodes(treeData.value).some(node => node.status === 'uploading' || node.status === 'parsing_sources');
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    uploading: '上传中',
    parsing_sources: '解析中',
    source_failed: '来源失败',
    sources_ready: '来源就绪',
    aligning: '字段对齐中',
    review_required: '待人工处理',
    yaml_ready: 'YAML 就绪',
    released: '已发布',
    completed: '解析完成',
    review_ready: '待审核',
    failed: '解析失败',
    waiting_for_step: '等待 STEP',
    pending: '等待处理',
    future: '后续能力'
  };
  return labels[status] || status;
}

function futureLabel(nodeType: Api.ComponentBuild.NodeType) {
  if (nodeType === 'fusion') return '数据融合';
  if (nodeType === 'yaml') return 'ComponentSpec';
  return '后续能力';
}

function isFailure(status: string) {
  return status === 'failed' || status === 'source_failed';
}

function nodeIconClass(node: ComponentTreeNode) {
  if (node.node_type === 'reference_step') return 'step';
  if (node.node_type === 'drawing') return 'drawing';
  if (node.node_type === 'fusion' || node.node_type === 'yaml' || node.node_type === 'future') return 'future';
  if (node.node_type === 'folder') return 'folder';
  return 'build';
}

function filterTree(keyword: string, data: unknown) {
  const node = data as ComponentTreeNode;
  if (!keyword) return true;
  const normalized = keyword.trim().toLowerCase();
  return `${node.label} ${node.status}`.toLowerCase().includes(normalized);
}

function formatProgress(progress: number | null | undefined) {
  return typeof progress === 'number' ? `${Math.round(progress)}%` : '';
}

function formatError(error: unknown, fallback: string) {
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object') {
    const data = error as { message?: string; response?: { data?: { detail?: string | { message?: string } } } };
    const detail = data.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail?.message) return detail.message;
    if (data.message) return data.message;
  }
  return fallback;
}

async function loadSelectedBuild(buildId: string): Promise<boolean> {
  if (!buildId) {
    selectedBuild.value = null;
    return true;
  }
  const [detailResult, statusResult] = await Promise.all([fetchComponentBuild(buildId), fetchComponentBuildStatus(buildId)]);
  if (!detailResult.error && detailResult.data) selectedBuild.value = detailResult.data;
  if (!statusResult.error && statusResult.data) {
    buildStatuses.value = { ...buildStatuses.value, [buildId]: statusResult.data };
  }
  return !detailResult.error && Boolean(detailResult.data) && !statusResult.error && Boolean(statusResult.data);
}

async function restoreSelectionFromRoute() {
  const buildId = typeof route.query.build_id === 'string' ? route.query.build_id : '';
  if (!buildId || !findNodeById(treeData.value, buildId)) return;
  selectedNodeId.value = buildId;
  await loadSelectedBuild(buildId);
  await nextTick();
  treeRef.value?.setCurrentKey(buildId);
  treeRef.value?.getNode(buildId)?.expand?.();
}

async function loadTree(options: { preserveSelection?: boolean; silent?: boolean } = {}): Promise<boolean> {
  treeLoading.value = true;
  try {
    const result = await fetchComponentBuildTree();
    if (result.error || !result.data) {
      if (!options.silent) window.$message?.error('图元建库树暂时不可用');
      return false;
    }
    treeData.value = normalizeTree(result.data as unknown as RawTreeNode[]);
    if (!options.preserveSelection || !selectedNode.value) await restoreSelectionFromRoute();
    return true;
  } finally {
    treeLoading.value = false;
  }
}

async function refresh() {
  refreshing.value = true;
  try {
    const treeOk = await loadTree({ preserveSelection: true });
    const buildOk = selectedBuildId.value ? await loadSelectedBuild(selectedBuildId.value) : true;
    statusUnavailable.value = !(treeOk && buildOk);
  } finally {
    refreshing.value = false;
  }
}

async function pollBuilds() {
  if (polling.value) return;
  const pending = allBuildNodes(treeData.value).filter(node => node.status === 'uploading' || node.status === 'parsing_sources');
  if (!pending.length) return;
  polling.value = true;
  try {
    const results = await Promise.all(pending.map(node => fetchComponentBuildStatus(node.id)));
    const next = { ...buildStatuses.value };
    results.forEach((result, index) => {
      if (!result.error && result.data) next[pending[index].id] = result.data;
    });
    buildStatuses.value = next;
    const statusesOk = results.every(result => !result.error && Boolean(result.data));
    const treeOk = await loadTree({ preserveSelection: true, silent: true });
    const buildOk = selectedBuildId.value ? await loadSelectedBuild(selectedBuildId.value) : true;
    statusUnavailable.value = !(statusesOk && treeOk && buildOk);
  } finally {
    polling.value = false;
  }
}

function syncPolling() {
  if (hasPendingBuilds() && !pollTimer.value) {
    pollTimer.value = window.setInterval(() => {
      void pollBuilds();
    }, 2000);
  }
  if (!hasPendingBuilds() && pollTimer.value) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

async function selectNode(data: ComponentTreeNode) {
  selectedNodeId.value = data.id;
  const buildId = data.node_type === 'build' ? data.id : data.build_id || '';
  await loadSelectedBuild(buildId);
}

function openCreateDrawer(build?: Api.ComponentBuild.BuildDetail | null) {
  form.value = build
    ? {
        component_id: build.component_id,
        component_name: build.component_name,
        component_type: build.component_type,
        component_subtype: build.component_subtype || '',
        family: build.family || '',
        standard_number: build.standard_number || '',
        version: build.version,
        default_dn: build.default_dn ?? undefined,
        default_pn: build.default_pn ?? undefined
      }
    : createDefaultForm();
  stepFile.value = null;
  drawingFile.value = null;
  drawerVisible.value = true;
  void nextTick(() => formRef.value?.clearValidate());
}

function pickFile(role: 'step' | 'drawing', event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] || null;
  if (!file) return;
  const valid = role === 'step' ? /\.(step|stp)$/i.test(file.name) : /\.(png|jpe?g|webp)$/i.test(file.name);
  if (!valid) {
    window.$message?.error(role === 'step' ? '请选择 STEP 或 STP 文件' : '请选择 PNG、JPG、JPEG 或 WEBP 图纸');
    (event.target as HTMLInputElement).value = '';
    return;
  }
  if (role === 'step') stepFile.value = file;
  else drawingFile.value = file;
}

async function submitBuild() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  if (!stepFile.value || !drawingFile.value) {
    window.$message?.warning('请同时选择 STEP 文件和二维图纸');
    return;
  }
  submitting.value = true;
  try {
    const result = await createComponentBuild({ ...form.value, step_file: stepFile.value, drawing_file: drawingFile.value });
    if (result.error || !result.data) throw result.error;
    drawerVisible.value = false;
    await router.replace({ path: '/component-build', query: { build_id: result.data.id } });
    await loadTree();
    window.$message?.success('图元建库任务已提交');
  } catch (error) {
    window.$message?.error(formatError(error, '图元建库提交失败'));
  } finally {
    submitting.value = false;
  }
}

function viewSourceResult() {
  const node = selectedNode.value;
  if (!node?.target || !node.build_id) return;
  if (node.node_type === 'reference_step' && node.target.revision_id) {
    void router.push({ path: '/cad-model', query: { revision_id: node.target.revision_id, build_id: node.build_id } });
  }
  if (node.node_type === 'drawing' && node.target.revision_id && node.target.task_id) {
    void router.push({
      path: '/cad-spec',
      query: { revision_id: node.target.revision_id, task_id: node.target.task_id, build_id: node.build_id }
    });
  }
}

function reuploadStep() {
  window.$message?.warning('当前接口要求新建图元并重新上传 STEP；原失败记录会保留用于审计。');
  openCreateDrawer(selectedBuild.value);
}

async function retryDrawing() {
  if (!selectedBuildId.value) return;
  retrying.value = true;
  try {
    const result = await retryComponentBuild(selectedBuildId.value, 'drawing');
    if (result.error) throw result.error;
    await refresh();
    window.$message?.success('二维图纸已重新进入解析队列');
  } catch (error) {
    window.$message?.error(formatError(error, '二维图纸重试失败'));
  } finally {
    retrying.value = false;
  }
}

function handleResize() {
  viewportWidth.value = window.innerWidth;
}

watch(searchKeyword, value => treeRef.value?.filter(value));
watch(treeData, syncPolling, { deep: true });

onMounted(async () => {
  window.addEventListener('resize', handleResize);
  statusUnavailable.value = !(await loadTree());
  syncPolling();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  if (pollTimer.value) window.clearInterval(pollTimer.value);
});
</script>

<template>
  <div class="component-build-page">
    <header class="workbench-toolbar">
      <div class="toolbar-title">
        <span>图元建库</span>
        <small>图纸与 STEP 成套解析</small>
      </div>
      <div class="toolbar-actions">
        <ElInput v-model="searchKeyword" clearable class="tree-search" placeholder="搜索图元、文件或状态">
          <template #prefix><icon-ic-round-search /></template>
        </ElInput>
        <ElTooltip content="刷新树和解析状态" placement="bottom">
          <ElButton :loading="refreshing" circle @click="refresh">
            <template #icon><icon-ic-round-refresh /></template>
          </ElButton>
        </ElTooltip>
        <ElButton type="primary" @click="openCreateDrawer()">
          <template #icon><icon-ic-round-add /></template>
          新建图元
        </ElButton>
      </div>
    </header>

    <main class="workbench-shell">
      <aside class="tree-panel" aria-label="图元建库文件树">
        <div class="panel-heading">
          <span>文件树</span>
          <span class="heading-count">{{ allBuildNodes(treeData).length }}</span>
        </div>
        <div v-loading="treeLoading" class="tree-body">
          <ElEmpty v-if="!treeLoading && !treeData.length" description="暂无图元建库任务" :image-size="58">
            <ElButton type="primary" size="small" @click="openCreateDrawer()">新建图元</ElButton>
          </ElEmpty>
          <ElTree
            v-else
            ref="treeRef"
            :data="treeData"
            node-key="id"
            highlight-current
            :filter-node-method="filterTree"
            :props="{ children: 'children', label: 'label', disabled: 'disabled' }"
            @node-click="selectNode"
          >
            <template #default="{ data }">
              <div class="tree-node" :class="{ disabled: data.disabled }">
                <span class="node-icon" :class="nodeIconClass(data)">
                  <icon-carbon-document v-if="data.node_type === 'reference_step'" />
                  <icon-carbon-image v-else-if="data.node_type === 'drawing'" />
                  <icon-carbon-folder v-else-if="data.node_type === 'folder'" />
                  <icon-carbon-cube v-else-if="data.node_type === 'build'" />
                  <icon-carbon-time v-else />
                </span>
                <span class="tree-node-label">{{ data.label }}</span>
                <span class="status-dot" :class="data.status" />
                <span v-if="formatProgress(data.progress)" class="tree-progress">{{ formatProgress(data.progress) }}</span>
              </div>
            </template>
          </ElTree>
        </div>
      </aside>

      <section class="detail-panel">
        <ElAlert
          v-if="statusUnavailable"
          class="status-alert"
          title="解析状态暂时不可用，页面保留上次成功结果并继续重试。"
          type="warning"
          :closable="false"
          show-icon
        />
        <ElEmpty v-if="!selectedNode" description="在左侧选择图元或文件查看详情" :image-size="62" />

        <template v-else-if="isFutureNode">
          <div class="detail-heading">
            <div>
              <span class="eyebrow">{{ selectedNode.status_label || '后续能力' }}</span>
              <h1>{{ selectedNode.label }}</h1>
            </div>
            <ElTag type="info" effect="plain">后续能力</ElTag>
          </div>
          <section class="detail-section muted-section">
            <p>该节点依赖字段融合、ComponentSpec 生成或发布校验能力；当前阶段不会把它显示为已完成。</p>
          </section>
        </template>

        <template v-else-if="isSourceNode">
          <div class="detail-heading">
            <div>
              <span class="eyebrow">来源文件</span>
              <h1 :title="selectedNode.label">{{ selectedNode.label }}</h1>
            </div>
            <ElTag :type="isFailure(selectedNode.status) ? 'danger' : selectedNode.status === 'completed' || selectedNode.status === 'review_ready' ? 'success' : 'info'">
              {{ statusLabel(selectedNode.status) }}
            </ElTag>
          </div>
          <section class="detail-section source-summary">
            <dl>
              <div><dt>解析阶段</dt><dd>{{ sourceStatus?.status_message || selectedNode.status_message || statusLabel(selectedNode.status) }}</dd></div>
              <div v-if="sourceStatus?.progress !== null && sourceStatus?.progress !== undefined"><dt>真实进度</dt><dd>{{ formatProgress(sourceStatus.progress) }}</dd></div>
              <div><dt>关联版本</dt><dd class="mono">{{ selectedNode.build_id || '-' }}</dd></div>
            </dl>
            <ElProgress
              v-if="sourceStatus?.progress !== null && sourceStatus?.progress !== undefined"
              :percentage="sourceStatus.progress"
              :status="isFailure(selectedNode.status) ? 'exception' : undefined"
              :stroke-width="8"
            />
          </section>
          <section v-if="selectedNode.error_message || sourceStatus?.error_message" class="detail-section error-section">
            <span class="section-label">错误信息</span>
            <p>{{ selectedNode.error_message || sourceStatus?.error_message }}</p>
          </section>
          <footer class="detail-actions">
            <ElButton v-if="canViewSource" type="primary" @click="viewSourceResult">查看解析结果</ElButton>
            <ElButton v-if="canRetryDrawing" :loading="retrying" @click="retryDrawing">重试二维图纸</ElButton>
            <ElButton v-if="canReuploadStep" @click="reuploadStep">重新上传 STEP</ElButton>
            <span v-if="!canViewSource && !canRetryDrawing && !canReuploadStep" class="action-hint">解析达到可查看状态后可进入专业页面。</span>
          </footer>
        </template>

        <template v-else>
          <div class="detail-heading">
            <div>
              <span class="eyebrow">图元建库版本</span>
              <h1>{{ selectedBuild?.component_name || selectedNode.label }}</h1>
            </div>
            <ElTag :type="isFailure(selectedBuild?.status || selectedNode.status) ? 'danger' : 'info'">
              {{ statusLabel(selectedBuild?.status || selectedNode.status) }}
            </ElTag>
          </div>
          <section class="detail-section build-summary">
            <dl>
              <div><dt>图元 ID</dt><dd>{{ selectedBuild?.component_id || '-' }}</dd></div>
              <div><dt>版本</dt><dd>{{ selectedBuild?.version || '-' }}</dd></div>
              <div><dt>分类</dt><dd>{{ [selectedBuild?.family, selectedBuild?.component_type, selectedBuild?.component_subtype].filter(Boolean).join(' / ') || '-' }}</dd></div>
              <div><dt>标准</dt><dd>{{ selectedBuild?.standard_number || '-' }}</dd></div>
              <div><dt>默认规格</dt><dd>{{ selectedBuild?.default_dn ? `DN${selectedBuild.default_dn}` : '-' }} {{ selectedBuild?.default_pn ? `PN${selectedBuild.default_pn}` : '' }}</dd></div>
            </dl>
          </section>
          <section class="detail-section pipeline-section">
            <div class="section-title">建库流水线</div>
            <ol class="pipeline-list">
              <li><span class="pipeline-dot" :class="selectedBuild?.status || selectedNode.status" /><span>成套文件提交</span><small>{{ statusLabel(selectedBuild?.status || selectedNode.status) }}</small></li>
              <li><span class="pipeline-dot" :class="selectedBuildStatus?.sources.reference_step.status || 'pending'" /><span>STEP 几何解析</span><small>{{ statusLabel(selectedBuildStatus?.sources.reference_step.status || 'pending') }}</small></li>
              <li><span class="pipeline-dot" :class="selectedBuildStatus?.sources.drawing.status || 'pending'" /><span>二维图纸抽取</span><small>{{ statusLabel(selectedBuildStatus?.sources.drawing.status || 'pending') }}</small></li>
              <li><span class="pipeline-dot future" /><span>字段融合</span><small>后续能力</small></li>
              <li><span class="pipeline-dot future" /><span>ComponentSpec</span><small>待生成</small></li>
            </ol>
          </section>
          <section v-if="selectedBuild?.error_message" class="detail-section error-section">
            <span class="section-label">错误信息</span>
            <p>{{ selectedBuild.error_message }}</p>
          </section>
        </template>
      </section>
    </main>

    <ElDrawer v-model="drawerVisible" :size="drawerSize" title="新建图元建库任务" destroy-on-close>
      <ElForm ref="formRef" :model="form" :rules="formRules" label-position="top">
        <div class="form-grid">
          <ElFormItem label="图元 ID" prop="component_id"><ElInput v-model="form.component_id" placeholder="例如 XMS06" /></ElFormItem>
          <ElFormItem label="图元名称" prop="component_name"><ElInput v-model="form.component_name" placeholder="例如 带颈对焊法兰" /></ElFormItem>
          <ElFormItem label="图元类型" prop="component_type"><ElInput v-model="form.component_type" placeholder="例如 法兰" /></ElFormItem>
          <ElFormItem label="子类型"><ElInput v-model="form.component_subtype" placeholder="可选" /></ElFormItem>
          <ElFormItem label="产品族"><ElInput v-model="form.family" placeholder="可选" /></ElFormItem>
          <ElFormItem label="标准号"><ElInput v-model="form.standard_number" placeholder="可选" /></ElFormItem>
          <ElFormItem label="版本"><ElInput v-model="form.version" /></ElFormItem>
          <ElFormItem label="默认 DN"><ElInputNumber v-model="form.default_dn" :min="0" controls-position="right" class="number-input" /></ElFormItem>
          <ElFormItem label="默认 PN"><ElInputNumber v-model="form.default_pn" :min="0" controls-position="right" class="number-input" /></ElFormItem>
        </div>
        <section class="upload-field">
          <span class="upload-label">参考 STEP <b>*</b></span>
          <label class="file-input"><input accept=".step,.stp" type="file" @change="pickFile('step', $event)" /><span>{{ stepFile?.name || '选择 STEP / STP 文件' }}</span></label>
        </section>
        <section class="upload-field">
          <span class="upload-label">二维参数图 <b>*</b></span>
          <label class="file-input"><input accept=".png,.jpg,.jpeg,.webp" type="file" @change="pickFile('drawing', $event)" /><span>{{ drawingFile?.name || '选择 PNG、JPG、JPEG 或 WEBP 图纸' }}</span></label>
        </section>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitBuild">提交成套资料</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped>
.component-build-page { display: flex; min-height: 100%; flex-direction: column; gap: 12px; padding: 12px; color: var(--el-text-color-primary); }
.workbench-toolbar { display: flex; min-height: 48px; align-items: center; justify-content: space-between; gap: 16px; padding: 0 4px; }
.toolbar-title { display: flex; align-items: baseline; gap: 10px; font-size: 16px; font-weight: 600; white-space: nowrap; }
.toolbar-title small { color: var(--el-text-color-secondary); font-size: 12px; font-weight: 400; }
.toolbar-actions { display: flex; align-items: center; gap: 8px; }
.tree-search { width: min(280px, 34vw); }
.workbench-shell { display: grid; min-height: 0; flex: 1; grid-template-columns: 320px minmax(0, 1fr); gap: 12px; }
.tree-panel, .detail-panel { min-width: 0; border: 1px solid var(--el-border-color-light); background: var(--el-bg-color); }
.tree-panel { display: flex; min-height: 640px; flex-direction: column; }
.panel-heading { display: flex; height: 42px; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--el-border-color-lighter); padding: 0 12px; font-size: 13px; font-weight: 600; }
.heading-count { color: var(--el-text-color-secondary); font-size: 12px; font-weight: 400; }
.tree-body { min-height: 0; flex: 1; overflow: auto; padding: 6px 4px; }
.tree-body :deep(.el-tree) { background: transparent; }
.tree-body :deep(.el-tree-node__content) { height: 32px; min-width: 0; }
.tree-node { display: grid; width: 100%; min-width: 0; grid-template-columns: 18px minmax(0, 1fr) 7px auto; align-items: center; gap: 6px; padding-right: 6px; }
.tree-node.disabled { color: var(--el-text-color-placeholder); cursor: not-allowed; }
.node-icon { display: inline-flex; color: var(--el-text-color-secondary); font-size: 15px; }
.node-icon.step { color: var(--el-color-primary); }.node-icon.drawing { color: var(--el-color-success); }.node-icon.folder { color: var(--el-color-warning); }.node-icon.future { color: var(--el-text-color-placeholder); }
.tree-node-label, .mono { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.status-dot, .pipeline-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--el-text-color-placeholder); }.status-dot.completed, .status-dot.review_ready, .status-dot.sources_ready, .pipeline-dot.completed, .pipeline-dot.review_ready, .pipeline-dot.sources_ready { background: var(--el-color-success); }.status-dot.uploading, .status-dot.parsing_sources, .status-dot.processing, .status-dot.queued, .pipeline-dot.uploading, .pipeline-dot.parsing_sources, .pipeline-dot.processing, .pipeline-dot.queued { background: var(--el-color-primary); }.status-dot.failed, .status-dot.source_failed, .pipeline-dot.failed, .pipeline-dot.source_failed { background: var(--el-color-danger); }.status-dot.review_required, .status-dot.needs_manual_layout, .pipeline-dot.review_required, .pipeline-dot.needs_manual_layout { background: var(--el-color-warning); }.status-dot.future, .pipeline-dot.future { background: var(--el-text-color-placeholder); }
.tree-progress { color: var(--el-text-color-secondary); font-size: 11px; font-variant-numeric: tabular-nums; }
.detail-panel { min-height: 640px; overflow: auto; padding: 20px 24px; }
.status-alert { margin-bottom: 16px; }
.detail-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 16px; }.detail-heading h1 { max-width: min(680px, 64vw); margin: 3px 0 0; overflow: hidden; font-size: 18px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }.eyebrow { color: var(--el-text-color-secondary); font-size: 12px; }.detail-section { border-bottom: 1px solid var(--el-border-color-lighter); padding: 18px 0; }.detail-section p { max-width: 760px; margin: 8px 0 0; color: var(--el-text-color-regular); line-height: 1.7; }.muted-section { color: var(--el-text-color-secondary); }.detail-section dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 32px; margin: 0; }.detail-section dl div { min-width: 0; }.detail-section dt { margin-bottom: 4px; color: var(--el-text-color-secondary); font-size: 12px; }.detail-section dd { margin: 0; overflow: hidden; line-height: 1.5; text-overflow: ellipsis; white-space: nowrap; }.source-summary :deep(.el-progress) { max-width: 520px; margin-top: 18px; }.error-section { border-left: 3px solid var(--el-color-danger); padding-left: 12px; }.error-section p { overflow-wrap: anywhere; color: var(--el-color-danger); }.section-label, .section-title { color: var(--el-text-color-secondary); font-size: 12px; font-weight: 600; }.pipeline-list { display: grid; gap: 0; margin: 14px 0 0; padding: 0; list-style: none; }.pipeline-list li { display: grid; min-height: 34px; grid-template-columns: 16px minmax(0, 1fr) auto; align-items: center; gap: 8px; }.pipeline-list small { color: var(--el-text-color-secondary); font-size: 12px; }.detail-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 18px; }.action-hint { color: var(--el-text-color-secondary); font-size: 13px; }.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 12px; }.number-input { width: 100%; }.upload-field { margin-top: 18px; }.upload-label { display: block; margin-bottom: 8px; font-size: 13px; }.upload-label b { color: var(--el-color-danger); }.file-input { display: block; position: relative; overflow: hidden; border: 1px dashed var(--el-border-color); padding: 10px 12px; color: var(--el-text-color-regular); cursor: pointer; }.file-input:hover { border-color: var(--el-color-primary); }.file-input input { position: absolute; inset: 0; width: 100%; opacity: 0; cursor: pointer; }.file-input span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 700px) { .component-build-page { padding: 8px; }.workbench-toolbar { align-items: flex-start; flex-direction: column; gap: 8px; }.toolbar-actions { width: 100%; }.tree-search { width: auto; flex: 1; }.workbench-shell { grid-template-columns: minmax(0, 1fr); }.tree-panel, .detail-panel { min-height: 360px; }.tree-panel { max-height: 420px; }.detail-panel { padding: 16px; }.detail-heading h1 { max-width: 64vw; }.detail-section dl { grid-template-columns: minmax(0, 1fr); gap: 12px; }.form-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
