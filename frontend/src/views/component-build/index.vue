<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import {
  createComponentBuild,
  fetchComponentBuild,
  fetchComponentBuildCatalog,
  fetchComponentBuildStatus,
  fetchComponentBuildTree,
  fetchComponentSpec,
  previewComponentSpec,
  retryComponentBuild,
  saveComponentSpec,
  updateComponentBuild
} from '@/service/api';
import componentSpecFallbackSource from './component-spec-v1.2.json';
import ComponentSpecFieldEditor from './modules/ComponentSpecFieldEditor.vue';

defineOptions({ name: 'ComponentBuild' });

type ComponentTreeNode = Api.ComponentBuild.TreeNode;
type RawTreeNode = Api.ComponentBuild.RawTreeNode;

const route = useRoute();
const router = useRouter();
const requestController = new AbortController();
const treeRef = ref<{
  filter: (keyword: string) => void;
  getNode: (key: string) => { expand?: () => void } | undefined;
  setCurrentKey: (key?: string) => void;
}>();
const formRef = ref<FormInstance>();

const treeLoading = ref(false);
const catalogLoading = ref(false);
const refreshing = ref(false);
const submitting = ref(false);
const parsingRole = ref<Api.ComponentBuild.RetryRole | null>(null);
const drawerVisible = ref(false);
const searchKeyword = ref('');
const treeData = ref<ComponentTreeNode[]>([]);
const catalog = ref<Api.ComponentBuild.CatalogCategory[]>([]);
const selectedNodeId = ref('');
const expandedNodeIds = ref<string[]>([]);
const selectedBuild = ref<Api.ComponentBuild.BuildDetail | null>(null);
const buildStatuses = ref<Record<string, Api.ComponentBuild.BuildStatus>>({});
const pollTimer = ref<number | null>(null);
const polling = ref(false);
const statusUnavailable = ref(false);
const viewportWidth = ref(window.innerWidth);
const componentSpec = ref<Api.ComponentBuild.ComponentSpecDocument | null>(null);
const componentSpecLoading = ref(false);
const componentSpecSaving = ref(false);
const componentSpecDirty = ref(false);
const componentSpecOffline = ref(false);
const componentSpecPreviewing = ref(false);
const componentSpecPreviewVisible = ref(false);
const componentSpecYaml = ref('');
const activeSpecSections = ref<string[]>([]);

const componentSpecFallback = componentSpecFallbackSource as Api.ComponentBuild.ComponentSpecDocument;

const form = ref(createDefaultForm());
const stepFile = ref<File | null>(null);
const drawingFile = ref<File | null>(null);
const editingBuild = ref<Api.ComponentBuild.BuildDetail | null>(null);

const formRules: FormRules = {
  category_code: [{ required: true, message: '请选择大类', trigger: 'change' }],
  part_type_code: [{ required: true, message: '请选择部件类型', trigger: 'change' }],
  component_name: [{ required: true, message: '请输入图元名称', trigger: 'blur' }],
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
const isCatalogNode = computed(() => selectedNode.value?.node_type === 'family' || selectedNode.value?.node_type === 'type');
const isComponentNode = computed(() => selectedNode.value?.node_type === 'component');
const isComponentSpecNode = computed(() => selectedNode.value?.node_type === 'component_spec');
const drawerSize = computed(() => (viewportWidth.value < 520 ? '100%' : 440));
const isEditing = computed(() => Boolean(editingBuild.value));
const drawerTitle = computed(() => (isEditing.value ? '编辑图元' : '新建图元'));
const selectedCategory = computed(
  () => catalog.value.find(item => item.category_code === form.value.category_code) || null
);
const availablePartTypes = computed(() => selectedCategory.value?.parts || []);
const selectedPartType = computed(
  () => availablePartTypes.value.find(item => item.part_type_code === form.value.part_type_code) || null
);
const selectedCatalogPath = computed(() => {
  const labels = [selectedCategory.value?.label, selectedPartType.value?.label].filter(Boolean);
  return labels.length ? `/${labels.join('/')}` : '请先选择大类和部件类型';
});
const generatedIdPreview = computed(() =>
  editingBuild.value
    ? editingBuild.value.component_id
    : selectedPartType.value
      ? `${selectedPartType.value.id_prefix}-###（系统自动递增）`
      : '选择部件类型后自动生成'
);

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

const canReuploadBuildStep = computed(
  () =>
    !isSourceNode.value &&
    selectedBuild.value?.status === 'source_failed' &&
    !selectedBuild.value.cad_revision_id
);
const canHandleManualLayout = computed(
  () =>
    selectedNode.value?.node_type === 'drawing' &&
    selectedNode.value.status === 'needs_manual_layout' &&
    Boolean(selectedNode.value.target?.revision_id && selectedNode.value.target?.task_id)
);

function createDefaultForm(): Omit<Api.ComponentBuild.CreatePayload, 'step_file' | 'drawing_file'> {
  return {
    category_code: '',
    part_type_code: '',
    component_name: '',
    standard_number: '',
    version: '1.0.0'
  };
}

function normalizeNodeType(nodeType?: string): Api.ComponentBuild.NodeType {
  const aliases: Record<string, Api.ComponentBuild.NodeType> = {
    data_fusion: 'fusion',
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
    'component_spec',
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
      label_en: node.label_en || null,
      node_type: nodeType,
      status: node.status || (nodeType === 'future' || nodeType === 'fusion' || nodeType === 'yaml' ? 'future' : 'pending'),
      progress: typeof node.progress === 'number' ? node.progress : null,
      disabled: Boolean(node.disabled) || nodeType === 'future' || nodeType === 'fusion' || nodeType === 'yaml',
      build_id: buildId,
      category_code: node.category_code || null,
      part_type_code: node.part_type_code || null,
      component_id: node.component_id || null,
      component_name: node.component_name || null,
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
    sources_partial: '部分来源就绪',
    aligning: '字段对齐中',
    review_required: '待人工处理',
    yaml_ready: 'YAML 就绪',
    saved: '已保存',
    released: '已发布',
    completed: '解析完成',
    review_ready: '待审核',
    failed: '解析失败',
    waiting_for_step: '等待 STEP',
    missing: '未上传',
    pending: '等待处理',
    future: '后续能力'
  };
  return labels[status] || status;
}

function futureLabel(nodeType: Api.ComponentBuild.NodeType) {
  if (nodeType === 'fusion') return '数据融合';
  if (nodeType === 'yaml' || nodeType === 'component_spec') return 'ComponentSpec';
  return '后续能力';
}

function isFailure(status: string) {
  return status === 'failed' || status === 'source_failed';
}

function sourceIsParsing(role: Api.ComponentBuild.RetryRole) {
  const source = selectedBuildStatus.value?.sources[role];
  if (!source) return false;
  return !['failed', 'completed', 'review_ready', 'needs_manual_layout', 'waiting_for_step', 'missing'].includes(
    source.status
  );
}

function canStartParsing(role: Api.ComponentBuild.RetryRole) {
  if (!selectedBuild.value || sourceIsParsing(role) || parsingRole.value !== null) return false;
  return role === 'reference_step'
    ? Boolean(selectedBuild.value.cad_revision_id)
    : Boolean(selectedBuild.value.drawing_task_id);
}

function nodeIconClass(node: ComponentTreeNode) {
  if (node.node_type === 'family' || node.node_type === 'type') return 'catalog';
  if (node.node_type === 'component') return 'component';
  if (node.node_type === 'reference_step') return 'step';
  if (node.node_type === 'drawing') return 'drawing';
  if (node.node_type === 'component_spec') return 'spec';
  if (node.node_type === 'fusion' || node.node_type === 'yaml' || node.node_type === 'future') return 'future';
  if (node.node_type === 'folder') return 'folder';
  return 'build';
}

function filterTree(keyword: string, data: unknown) {
  const node = data as ComponentTreeNode;
  if (!keyword) return true;
  const normalized = keyword.trim().toLowerCase();
  return [
    node.label,
    node.label_en,
    node.status,
    node.category_code,
    node.part_type_code,
    node.component_id,
    node.component_name
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
    .includes(normalized);
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

async function loadSelectedBuild(buildId: string, options: { silent?: boolean } = {}): Promise<boolean> {
  if (!buildId) {
    selectedBuild.value = null;
    return true;
  }
  const queryOptions = { signal: requestController.signal, silent: options.silent };
  const [detailResult, statusResult] = await Promise.all([
    fetchComponentBuild(buildId, queryOptions),
    fetchComponentBuildStatus(buildId, queryOptions)
  ]);
  if (requestController.signal.aborted) return false;
  if (!detailResult.error && detailResult.data) selectedBuild.value = detailResult.data;
  if (!statusResult.error && statusResult.data) {
    buildStatuses.value = { ...buildStatuses.value, [buildId]: statusResult.data };
  }
  return !detailResult.error && Boolean(detailResult.data) && !statusResult.error && Boolean(statusResult.data);
}

function componentSpecStorageKey(buildId: string) {
  return `component-spec-v1.2:${buildId}`;
}

function localComponentSpec(buildId: string): Api.ComponentBuild.ComponentSpecDocument {
  const document = structuredClone(componentSpecFallback);
  document.build_id = buildId;
  const saved = localStorage.getItem(componentSpecStorageKey(buildId));
  if (!saved) return document;
  try {
    const cached = JSON.parse(saved) as { data: Record<string, any>; updated_at: string };
    document.data = cached.data;
    document.saved = true;
    document.updated_at = cached.updated_at;
  } catch {
    localStorage.removeItem(componentSpecStorageKey(buildId));
  }
  return document;
}

function yamlScalar(value: any): string {
  if (value === null || value === undefined || value === '') return 'null';
  if (typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `[${value.map(item => yamlScalar(item)).join(', ')}]`;
  return String(value);
}

function yamlComment(field: Api.ComponentBuild.ComponentSpecField) {
  return field.comment ? `  # ${field.comment}` : '';
}

function renderYamlField(
  field: Api.ComponentBuild.ComponentSpecField,
  value: any,
  indent: number,
  sequencePrefix = ''
): string[] {
  const prefix = `${' '.repeat(indent)}${sequencePrefix}${field.key}:`;
  const childIndent = indent + (sequencePrefix ? 4 : 2);
  if (field.kind === 'object') {
    const lines = [`${prefix}${yamlComment(field)}`];
    for (const child of field.children || []) {
      lines.push(...renderYamlField(child, value?.[child.key], childIndent));
    }
    return lines;
  }
  if (field.kind === 'object_array') {
    const items = Array.isArray(value) ? value : [];
    if (!items.length) return [`${prefix} []${yamlComment(field)}`];
    const lines = [`${prefix}${yamlComment(field)}`];
    for (const item of items) {
      const children = field.item?.children || [];
      children.forEach((child, index) => {
        lines.push(
          ...renderYamlField(
            child,
            item?.[child.key],
            indent + (index === 0 ? 2 : 4),
            index === 0 ? '- ' : ''
          )
        );
      });
    }
    return lines;
  }
  return [`${prefix} ${yamlScalar(value)}${yamlComment(field)}`];
}

function renderLocalComponentSpecYaml(document: Api.ComponentBuild.ComponentSpecDocument) {
  const lines = [
    '# ComponentSpec v1.2',
    '# 本预览按 component-spec-v1.2-template.yaml 的字段顺序与中文注释生成。',
    ''
  ];
  document.schema.sections.forEach((section, index) => {
    lines.push(`# ── ${index + 1}. ${section.label} ──`);
    for (const field of section.fields) {
      lines.push(...renderYamlField(field, document.data[field.key], 0));
    }
    lines.push('');
  });
  return lines.join('\n');
}

async function loadComponentSpec(buildId: string) {
  if (!buildId) return;
  componentSpecLoading.value = true;
  try {
    const result = await fetchComponentSpec(buildId);
    if (result.error || !result.data) {
      componentSpec.value = localComponentSpec(buildId);
      componentSpecOffline.value = true;
    } else {
      componentSpec.value = result.data;
      componentSpecOffline.value = false;
    }
    componentSpecDirty.value = false;
    activeSpecSections.value = componentSpec.value.schema.sections.map(section => section.key);
  } catch {
    componentSpec.value = localComponentSpec(buildId);
    componentSpecOffline.value = true;
    componentSpecDirty.value = false;
    activeSpecSections.value = componentSpec.value.schema.sections.map(section => section.key);
  } finally {
    componentSpecLoading.value = false;
  }
}

function updateComponentSpecField(key: string, value: any) {
  if (!componentSpec.value) return;
  componentSpec.value.data = { ...componentSpec.value.data, [key]: value };
  componentSpecDirty.value = true;
}

async function saveCurrentComponentSpec() {
  if (!componentSpec.value || !selectedBuildId.value) return;
  componentSpecSaving.value = true;
  try {
    const result = await saveComponentSpec(selectedBuildId.value, componentSpec.value.data);
    if (result.error || !result.data) {
      const updatedAt = new Date().toISOString();
      localStorage.setItem(
        componentSpecStorageKey(selectedBuildId.value),
        JSON.stringify({ data: componentSpec.value.data, updated_at: updatedAt })
      );
      componentSpec.value = { ...componentSpec.value, saved: true, updated_at: updatedAt };
      componentSpecOffline.value = true;
      window.$message?.warning('后端模板接口尚未启用，草稿已暂存在当前浏览器');
    } else {
      componentSpec.value = result.data;
      componentSpecOffline.value = false;
      window.$message?.success('ComponentSpec 草稿已保存');
    }
    componentSpecDirty.value = false;
    await loadTree({ preserveSelection: true, silent: true });
  } catch (error) {
    window.$message?.error(formatError(error, 'ComponentSpec 保存失败'));
  } finally {
    componentSpecSaving.value = false;
  }
}

async function previewCurrentComponentSpec() {
  if (!componentSpec.value || !selectedBuildId.value) return;
  componentSpecPreviewing.value = true;
  try {
    const result = await previewComponentSpec(selectedBuildId.value, componentSpec.value.data);
    componentSpecYaml.value =
      !result.error && result.data
        ? result.data.yaml
        : renderLocalComponentSpecYaml(componentSpec.value);
    componentSpecPreviewVisible.value = true;
  } catch (error) {
    componentSpecYaml.value = renderLocalComponentSpecYaml(componentSpec.value);
    componentSpecPreviewVisible.value = true;
  } finally {
    componentSpecPreviewing.value = false;
  }
}

async function copyComponentSpecYaml() {
  await navigator.clipboard.writeText(componentSpecYaml.value);
  window.$message?.success('YAML 已复制');
}

async function restoreSelectionFromRoute() {
  const buildId = typeof route.query.build_id === 'string' ? route.query.build_id : '';
  if (!buildId || !findNodeById(treeData.value, buildId)) return;
  selectedNodeId.value = buildId;
  if (!expandedNodeIds.value.includes(buildId)) expandedNodeIds.value = [...expandedNodeIds.value, buildId];
  await loadSelectedBuild(buildId);
  await nextTick();
  treeRef.value?.setCurrentKey(buildId);
  treeRef.value?.getNode(buildId)?.expand?.();
}

async function loadTree(options: { preserveSelection?: boolean; silent?: boolean } = {}): Promise<boolean> {
  const showLoading = !options.silent;
  if (showLoading) treeLoading.value = true;
  try {
    const result = await fetchComponentBuildTree({
      signal: requestController.signal,
      silent: options.silent
    });
    if (requestController.signal.aborted) return false;
    if (result.error || !result.data) {
      if (!options.silent) window.$message?.error('图元建库树暂时不可用');
      return false;
    }
    treeData.value = normalizeTree(result.data);
    if (!options.preserveSelection || !selectedNode.value) await restoreSelectionFromRoute();
    await nextTick();
    expandedNodeIds.value.forEach(id => treeRef.value?.getNode(id)?.expand?.());
    return true;
  } finally {
    if (showLoading) treeLoading.value = false;
  }
}

async function loadCatalog(options: { silent?: boolean } = {}): Promise<boolean> {
  catalogLoading.value = true;
  try {
    const result = await fetchComponentBuildCatalog({
      signal: requestController.signal,
      silent: options.silent
    });
    if (requestController.signal.aborted) return false;
    if (result.error || !result.data) {
      if (!options.silent) window.$message?.error('图元分类目录暂时不可用');
      return false;
    }
    catalog.value = result.data.categories;
    return true;
  } finally {
    catalogLoading.value = false;
  }
}

async function refresh() {
  refreshing.value = true;
  try {
    const [treeOk, catalogOk] = await Promise.all([
      loadTree({ preserveSelection: true }),
      loadCatalog()
    ]);
    const buildOk = selectedBuildId.value ? await loadSelectedBuild(selectedBuildId.value) : true;
    statusUnavailable.value = !(treeOk && catalogOk && buildOk);
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
    const results = await Promise.all(
      pending.map(node =>
        fetchComponentBuildStatus(node.id, {
          signal: requestController.signal,
          silent: true
        })
      )
    );
    if (requestController.signal.aborted) return;
    const next = { ...buildStatuses.value };
    results.forEach((result, index) => {
      if (!result.error && result.data) next[pending[index].id] = result.data;
    });
    buildStatuses.value = next;
    const statusesOk = results.every(result => !result.error && Boolean(result.data));
    const treeOk = await loadTree({ preserveSelection: true, silent: true });
    const buildOk = selectedBuildId.value ? await loadSelectedBuild(selectedBuildId.value, { silent: true }) : true;
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
  if (data.node_type === 'component_spec') await loadComponentSpec(buildId);
}

function rememberExpanded(data: ComponentTreeNode) {
  if (!expandedNodeIds.value.includes(data.id)) expandedNodeIds.value = [...expandedNodeIds.value, data.id];
}

function forgetExpanded(data: ComponentTreeNode) {
  expandedNodeIds.value = expandedNodeIds.value.filter(id => id !== data.id);
}

function handleCategoryChange() {
  form.value.part_type_code = '';
  void nextTick(() => formRef.value?.clearValidate('part_type_code'));
}

function openCreateDrawer(build?: Api.ComponentBuild.BuildDetail | null) {
  const node = selectedNode.value;
  editingBuild.value = build || null;
  form.value = {
    category_code: build?.family || node?.category_code || '',
    part_type_code: build?.component_type || node?.part_type_code || '',
    component_name: build?.component_name || '',
    standard_number: build?.standard_number || '',
    version: build?.version || '1.0.0'
  };
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
  submitting.value = true;
  try {
    const payload = {
      ...form.value,
      ...(stepFile.value ? { step_file: stepFile.value } : {}),
      ...(drawingFile.value ? { drawing_file: drawingFile.value } : {})
    };
    const result = editingBuild.value
      ? await updateComponentBuild({ ...payload, build_id: editingBuild.value.id })
      : await createComponentBuild(payload);
    if (result.error || !result.data) throw result.error;
    drawerVisible.value = false;
    await router.replace({ path: '/component-build', query: { build_id: result.data.id } });
    await loadTree();
    await loadSelectedBuild(result.data.id);
    window.$message?.success(isEditing.value ? '图元修改已保存' : '图元已创建');
  } catch (error) {
    window.$message?.error(formatError(error, isEditing.value ? '图元修改保存失败' : '图元创建失败'));
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

function handleManualLayout() {
  const node = selectedNode.value;
  if (!node?.target?.revision_id || !node.target.task_id || !node.build_id) return;
  void router.push({
    path: '/cad-spec',
    query: {
      revision_id: node.target.revision_id,
      task_id: node.target.task_id,
      build_id: node.build_id
    }
  });
}

async function startParsing(role: Api.ComponentBuild.RetryRole) {
  if (!selectedBuild.value || !canStartParsing(role)) return;
  parsingRole.value = role;
  try {
    const result = await retryComponentBuild(selectedBuild.value.id, role);
    if (result.error) throw result.error;
    await refresh();
    window.$message?.success(role === 'reference_step' ? 'STEP 已进入解析队列' : '二维图纸已进入解析队列');
  } catch (error) {
    window.$message?.error(formatError(error, role === 'reference_step' ? 'STEP 解析启动失败' : '二维图纸解析启动失败'));
  } finally {
    parsingRole.value = null;
  }
}

function handleResize() {
  viewportWidth.value = window.innerWidth;
}

watch(searchKeyword, value => treeRef.value?.filter(value));
watch(treeData, syncPolling, { deep: true });

onMounted(async () => {
  window.addEventListener('resize', handleResize);
  const [treeOk, catalogOk] = await Promise.all([loadTree(), loadCatalog()]);
  statusUnavailable.value = !(treeOk && catalogOk);
  syncPolling();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  if (pollTimer.value) window.clearInterval(pollTimer.value);
  requestController.abort();
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
            :props="{ children: 'children', label: 'label', disabled: 'tree_disabled' }"
            @node-click="selectNode"
            @node-expand="rememberExpanded"
            @node-collapse="forgetExpanded"
          >
            <template #default="{ data }">
              <div class="tree-node" :class="{ disabled: data.disabled }">
                <span class="node-icon" :class="nodeIconClass(data)">
                  <icon-carbon-document v-if="data.node_type === 'reference_step'" />
                  <icon-carbon-image v-else-if="data.node_type === 'drawing'" />
                  <icon-carbon-document-requirements v-else-if="data.node_type === 'component_spec'" />
                  <icon-carbon-folder v-else-if="data.node_type === 'folder' || data.node_type === 'family' || data.node_type === 'type'" />
                  <icon-carbon-cube v-else-if="data.node_type === 'component' || data.node_type === 'build'" />
                  <icon-carbon-time v-else />
                </span>
                <span class="tree-node-label" :title="[data.label, data.label_en].filter(Boolean).join(' · ')">
                  {{ data.label }}
                  <small v-if="data.label_en" class="tree-node-en">{{ data.label_en }}</small>
                </span>
                <span
                  v-if="!['family', 'type', 'component'].includes(data.node_type)"
                  class="status-dot"
                  :class="data.status"
                />
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

        <template v-else-if="isCatalogNode">
          <div class="detail-heading">
            <div>
              <span class="eyebrow">{{ selectedNode.node_type === 'family' ? '图元大类' : '部件类型' }}</span>
              <h1>{{ selectedNode.label }}</h1>
              <p v-if="selectedNode.label_en" class="heading-subtitle">{{ selectedNode.label_en }}</p>
            </div>
          </div>
          <section class="detail-section catalog-summary">
            <dl>
              <div><dt>当前目录</dt><dd>/{{ selectedNode.label }}</dd></div>
              <div>
                <dt>{{ selectedNode.node_type === 'family' ? '部件类型数' : '图元实例数' }}</dt>
                <dd>{{ selectedNode.children.length }}</dd>
              </div>
            </dl>
            <p>
              {{
                selectedNode.node_type === 'family'
                  ? '新建时将预选该大类，再选择具体部件类型。'
                  : '新建图元会自动归档到当前部件类型，图元 ID 由系统生成。'
              }}
            </p>
          </section>
          <footer class="detail-actions">
            <ElButton type="primary" @click="openCreateDrawer()">在此分类新建图元</ElButton>
          </footer>
        </template>

        <template v-else-if="isComponentNode">
          <div class="detail-heading">
            <div>
              <span class="eyebrow">图元实例</span>
              <h1>{{ selectedNode.component_name || selectedNode.label }}</h1>
            </div>
          </div>
          <section class="detail-section build-summary">
            <dl>
              <div><dt>图元 ID</dt><dd class="mono">{{ selectedNode.component_id || '-' }}</dd></div>
              <div><dt>版本数</dt><dd>{{ selectedNode.children.length }}</dd></div>
            </dl>
            <p>展开图元并选择具体版本，可查看成套文件解析状态与结果。</p>
          </section>
        </template>

        <template v-else-if="isComponentSpecNode">
          <div class="detail-heading spec-heading">
            <div>
              <span class="eyebrow">图元规范表单 · v{{ componentSpec?.schema.schema_version || '1.2' }}</span>
              <h1>ComponentSpec</h1>
              <p class="heading-subtitle">
                {{ selectedBuild?.component_name || selectedNode.label }}
                <span v-if="componentSpec?.updated_at"> · 已保存</span>
                <span v-else> · 尚未保存</span>
                <span v-if="componentSpecDirty"> · 有未保存修改</span>
                <span v-if="componentSpecOffline"> · 本地模板模式</span>
              </p>
            </div>
            <div class="spec-actions">
              <ElButton
                :loading="componentSpecPreviewing"
                :disabled="!componentSpec"
                @click="previewCurrentComponentSpec"
              >
                <template #icon><icon-carbon-code /></template>
                预览 YAML
              </ElButton>
              <ElButton
                type="primary"
                :loading="componentSpecSaving"
                :disabled="!componentSpec"
                @click="saveCurrentComponentSpec"
              >
                <template #icon><icon-carbon-save /></template>
                保存草稿
              </ElButton>
            </div>
          </div>
          <div v-loading="componentSpecLoading" class="component-spec-body">
            <ElAlert
              :title="
                componentSpecOffline
                  ? '后端模板接口暂不可用，已加载内置的完整 v1.2 字段；保存时将暂存在当前浏览器。'
                  : '当前为人工填写草稿；后续解析结果将回填到同一份表单，仍可继续修改。'
              "
              :type="componentSpecOffline ? 'warning' : 'info'"
              :closable="false"
              show-icon
            />
            <ElCollapse v-if="componentSpec" v-model="activeSpecSections" class="spec-collapse">
              <ElCollapseItem
                v-for="(section, sectionIndex) in componentSpec.schema.sections"
                :key="section.key"
                :name="section.key"
              >
                <template #title>
                  <div class="spec-section-title">
                    <span>{{ sectionIndex + 1 }}</span>
                    <div>
                      <strong>{{ section.label }}</strong>
                      <small>{{ section.description }}</small>
                    </div>
                  </div>
                </template>
                <div class="spec-section-fields">
                  <ComponentSpecFieldEditor
                    v-for="field in section.fields"
                    :key="field.path"
                    :field="field"
                    :model-value="componentSpec.data[field.key]"
                    @update:model-value="updateComponentSpecField(field.key, $event)"
                  />
                </div>
              </ElCollapseItem>
            </ElCollapse>
          </div>
        </template>

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
            <ElButton v-if="canHandleManualLayout" type="primary" @click="handleManualLayout">处理版面</ElButton>
            <ElButton
              v-if="selectedNode.node_type === 'drawing' && selectedBuild?.drawing_task_id"
              :loading="parsingRole === 'drawing'"
              :disabled="!canStartParsing('drawing')"
              @click="startParsing('drawing')"
            >
              开始解析
            </ElButton>
            <ElButton v-if="selectedBuild" @click="openCreateDrawer(selectedBuild)">编辑图元</ElButton>
            <span
              v-if="!canViewSource && !canHandleManualLayout && !selectedBuild"
              class="action-hint"
            >
              解析达到可查看状态后可进入专业页面。
            </span>
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
              <div><dt>图元 ID（系统生成）</dt><dd class="mono">{{ selectedBuild?.component_id || '-' }}</dd></div>
              <div><dt>版本</dt><dd>{{ selectedBuild?.version || '-' }}</dd></div>
              <div><dt>归档路径</dt><dd>{{ selectedBuild?.catalog_path || '-' }}</dd></div>
              <div><dt>标准</dt><dd>{{ selectedBuild?.standard_number || '-' }}</dd></div>
            </dl>
          </section>
          <section class="detail-section pipeline-section">
            <div class="section-title">建库流水线</div>
            <ol class="pipeline-list">
              <li>
                <span class="pipeline-dot" :class="selectedBuild?.status || selectedNode.status" />
                <span>成套文件提交</span>
                <small>{{ statusLabel(selectedBuild?.status || selectedNode.status) }}</small>
                <span />
              </li>
              <li>
                <span class="pipeline-dot" :class="selectedBuildStatus?.sources.reference_step.status || 'pending'" />
                <span>STEP 几何解析</span>
                <small>{{ statusLabel(selectedBuildStatus?.sources.reference_step.status || 'pending') }}</small>
                <ElButton
                  size="small"
                  :loading="parsingRole === 'reference_step'"
                  :disabled="!canStartParsing('reference_step')"
                  :title="selectedBuild?.cad_revision_id ? '重新启动 STEP 几何解析' : '请先编辑并上传 STEP 文件'"
                  @click="startParsing('reference_step')"
                >
                  开始解析
                </ElButton>
              </li>
              <li>
                <span class="pipeline-dot" :class="selectedBuildStatus?.sources.drawing.status || 'pending'" />
                <span>二维图纸抽取</span>
                <small>{{ statusLabel(selectedBuildStatus?.sources.drawing.status || 'pending') }}</small>
                <ElButton
                  size="small"
                  :loading="parsingRole === 'drawing'"
                  :disabled="!canStartParsing('drawing')"
                  :title="selectedBuild?.drawing_task_id ? '重新启动二维图纸解析' : '请先编辑并上传二维图纸'"
                  @click="startParsing('drawing')"
                >
                  开始解析
                </ElButton>
              </li>
              <li><span class="pipeline-dot future" /><span>字段融合</span><small>后续能力</small><span /></li>
              <li><span class="pipeline-dot future" /><span>ComponentSpec</span><small>待生成</small><span /></li>
            </ol>
          </section>
          <section v-if="selectedBuild?.error_message" class="detail-section error-section">
            <span class="section-label">错误信息</span>
            <p>{{ selectedBuild.error_message }}</p>
          </section>
          <footer v-if="selectedBuild" class="detail-actions">
            <ElButton type="primary" @click="openCreateDrawer(selectedBuild)">编辑图元</ElButton>
            <span v-if="canReuploadBuildStep" class="action-hint">可在编辑抽屉中补传或替换来源文件。</span>
          </footer>
        </template>
      </section>
    </main>

    <ElDrawer v-model="drawerVisible" :size="drawerSize" :title="drawerTitle" destroy-on-close>
      <ElForm ref="formRef" v-loading="catalogLoading" :model="form" :rules="formRules" label-position="top">
        <div class="form-grid">
          <ElFormItem label="大类" prop="category_code">
            <ElSelect
              v-model="form.category_code"
              filterable
              class="field-control"
              placeholder="请选择大类"
              @change="handleCategoryChange"
            >
              <ElOption
                v-for="category in catalog"
                :key="category.category_code"
                :label="`${category.label} · ${category.label_en}`"
                :value="category.category_code"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="部件类型" prop="part_type_code">
            <ElSelect
              v-model="form.part_type_code"
              filterable
              class="field-control"
              :disabled="!form.category_code"
              placeholder="请先选择大类"
            >
              <ElOption
                v-for="part in availablePartTypes"
                :key="part.part_type_code"
                :label="`${part.label} · ${part.label_en}`"
                :value="part.part_type_code"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem class="form-span-2" label="归档路径">
            <ElInput :model-value="selectedCatalogPath" readonly />
          </ElFormItem>
          <ElFormItem label="图元名称" prop="component_name">
            <ElInput v-model="form.component_name" placeholder="例如 带颈对焊法兰" />
          </ElFormItem>
          <ElFormItem label="图元 ID">
            <ElInput :model-value="generatedIdPreview" readonly />
          </ElFormItem>
          <ElFormItem label="标准号"><ElInput v-model="form.standard_number" placeholder="可选" /></ElFormItem>
          <ElFormItem label="版本"><ElInput v-model="form.version" /></ElFormItem>
        </div>
        <section class="upload-field">
          <span class="upload-label">参考 STEP <small>可稍后补充</small></span>
          <label class="file-input">
            <input accept=".step,.stp" type="file" @change="pickFile('step', $event)" />
            <span>
              {{
                stepFile?.name ||
                (editingBuild?.cad_revision_id ? '已有关联 STEP；选择新文件可替换' : '选择 STEP / STP 文件')
              }}
            </span>
          </label>
        </section>
        <section class="upload-field">
          <span class="upload-label">二维参数图 <small>可稍后补充</small></span>
          <label class="file-input">
            <input accept=".png,.jpg,.jpeg,.webp" type="file" @change="pickFile('drawing', $event)" />
            <span>
              {{
                drawingFile?.name ||
                (editingBuild?.drawing_task_id ? '已有关联图纸；选择新文件可替换' : '选择 PNG、JPG、JPEG 或 WEBP 图纸')
              }}
            </span>
          </label>
          <p class="upload-hint">
            {{ isEditing ? '未选择新文件时保留当前来源。' : '可以先创建图元，之后再补传任意来源文件。' }}
          </p>
        </section>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" :disabled="catalogLoading || !catalog.length" @click="submitBuild">
          {{ isEditing ? '保存修改' : '创建图元' }}
        </ElButton>
      </template>
    </ElDrawer>

    <ElDrawer
      v-model="componentSpecPreviewVisible"
      title="ComponentSpec YAML 预览"
      :size="viewportWidth < 760 ? '100%' : '58%'"
    >
      <div class="yaml-preview-toolbar">
        <span>字段顺序、嵌套结构和中文注释均按 v1.2 模板生成</span>
        <ElButton size="small" @click="copyComponentSpecYaml">
          <template #icon><icon-carbon-copy /></template>
          复制
        </ElButton>
      </div>
      <pre class="yaml-preview">{{ componentSpecYaml }}</pre>
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
.node-icon.step { color: var(--el-color-primary); }.node-icon.drawing { color: var(--el-color-success); }.node-icon.folder, .node-icon.catalog { color: var(--el-color-warning); }.node-icon.component { color: var(--el-color-primary); }.node-icon.spec { color: #0f766e; }.node-icon.future { color: var(--el-text-color-placeholder); }
.tree-node-label, .mono { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.tree-node-en { margin-left: 4px; color: var(--el-text-color-secondary); font-size: 11px; }.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.status-dot, .pipeline-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--el-text-color-placeholder); }.status-dot.completed, .status-dot.review_ready, .status-dot.sources_ready, .status-dot.sources_partial, .pipeline-dot.completed, .pipeline-dot.review_ready, .pipeline-dot.sources_ready, .pipeline-dot.sources_partial { background: var(--el-color-success); }.status-dot.uploading, .status-dot.parsing_sources, .status-dot.processing, .status-dot.queued, .pipeline-dot.uploading, .pipeline-dot.parsing_sources, .pipeline-dot.processing, .pipeline-dot.queued { background: var(--el-color-primary); }.status-dot.failed, .status-dot.source_failed, .pipeline-dot.failed, .pipeline-dot.source_failed { background: var(--el-color-danger); }.status-dot.review_required, .status-dot.needs_manual_layout, .pipeline-dot.review_required, .pipeline-dot.needs_manual_layout { background: var(--el-color-warning); }.status-dot.future, .pipeline-dot.future { background: var(--el-text-color-placeholder); }
.tree-progress { color: var(--el-text-color-secondary); font-size: 11px; font-variant-numeric: tabular-nums; }
.detail-panel { min-height: 640px; overflow: auto; padding: 20px 24px; }
.status-alert { margin-bottom: 16px; }
.detail-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 16px; }.detail-heading h1 { max-width: min(680px, 64vw); margin: 3px 0 0; overflow: hidden; font-size: 18px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }.heading-subtitle { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }.eyebrow { color: var(--el-text-color-secondary); font-size: 12px; }.detail-section { border-bottom: 1px solid var(--el-border-color-lighter); padding: 18px 0; }.detail-section p { max-width: 760px; margin: 8px 0 0; color: var(--el-text-color-regular); line-height: 1.7; }.muted-section { color: var(--el-text-color-secondary); }.detail-section dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 32px; margin: 0; }.detail-section dl div { min-width: 0; }.detail-section dt { margin-bottom: 4px; color: var(--el-text-color-secondary); font-size: 12px; }.detail-section dd { margin: 0; overflow: hidden; line-height: 1.5; text-overflow: ellipsis; white-space: nowrap; }.source-summary :deep(.el-progress) { max-width: 520px; margin-top: 18px; }.error-section { border-left: 3px solid var(--el-color-danger); padding-left: 12px; }.error-section p { overflow-wrap: anywhere; color: var(--el-color-danger); }.section-label, .section-title { color: var(--el-text-color-secondary); font-size: 12px; font-weight: 600; }.pipeline-list { display: grid; gap: 0; margin: 14px 0 0; padding: 0; list-style: none; }.pipeline-list li { display: grid; min-height: 38px; grid-template-columns: 16px minmax(0, 1fr) minmax(70px, auto) 84px; align-items: center; gap: 8px; }.pipeline-list small { overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; text-align: right; text-overflow: ellipsis; white-space: nowrap; }.pipeline-list :deep(.el-button) { width: 84px; }.detail-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 18px; }.action-hint { color: var(--el-text-color-secondary); font-size: 13px; }.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 12px; }.form-span-2 { grid-column: 1 / -1; }.field-control { width: 100%; }.upload-field { margin-top: 18px; }.upload-label { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; font-size: 13px; }.upload-label small, .upload-hint { color: var(--el-text-color-secondary); font-size: 12px; }.upload-hint { margin: 7px 0 0; line-height: 1.5; }.file-input { display: block; position: relative; overflow: hidden; border: 1px dashed var(--el-border-color); padding: 10px 12px; color: var(--el-text-color-regular); cursor: pointer; }.file-input:hover { border-color: var(--el-color-primary); }.file-input input { position: absolute; inset: 0; width: 100%; opacity: 0; cursor: pointer; }.file-input span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.spec-heading { position: sticky; z-index: 5; top: -20px; align-items: center; margin: -20px -24px 0; background: var(--el-bg-color); padding: 18px 24px 14px; }
.spec-actions { display: flex; flex: none; gap: 8px; }
.component-spec-body { min-height: 460px; padding-top: 16px; }
.spec-collapse { margin-top: 14px; border-top: 1px solid var(--el-border-color-lighter); }
.spec-collapse :deep(.el-collapse-item__header) { min-height: 58px; height: auto; line-height: 1.4; }
.spec-collapse :deep(.el-collapse-item__content) { padding: 4px 4px 22px 42px; }
.spec-section-title { display: flex; min-width: 0; align-items: center; gap: 12px; }
.spec-section-title > span { display: grid; width: 26px; height: 26px; flex: none; place-items: center; border: 1px solid var(--el-border-color); border-radius: 4px; color: var(--el-text-color-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
.spec-section-title strong, .spec-section-title small { display: block; }
.spec-section-title strong { font-size: 14px; font-weight: 600; }
.spec-section-title small { margin-top: 2px; overflow: hidden; color: var(--el-text-color-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.spec-section-fields { display: grid; min-width: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }
.yaml-preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.yaml-preview { min-height: calc(100vh - 150px); margin: 0; overflow: auto; border: 1px solid var(--el-border-color-lighter); border-radius: 4px; background: #f7f8fa; padding: 16px; color: #20252b; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; line-height: 1.65; white-space: pre; }
@media (max-width: 700px) { .component-build-page { padding: 8px; }.workbench-toolbar { align-items: flex-start; flex-direction: column; gap: 8px; }.toolbar-actions { width: 100%; }.tree-search { width: auto; flex: 1; }.workbench-shell { grid-template-columns: minmax(0, 1fr); }.tree-panel, .detail-panel { min-height: 360px; }.tree-panel { max-height: 420px; }.detail-panel { padding: 16px; }.detail-heading h1 { max-width: 64vw; }.detail-section dl { grid-template-columns: minmax(0, 1fr); gap: 12px; }.form-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
