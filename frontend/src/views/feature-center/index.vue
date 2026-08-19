<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { fetchComponentBuildViewer, fetchComponentBuildViewerAsset, retryComponentBuild } from '@/service/api';
import { sha256Buffer } from './modules/asset-integrity';
import { facesForFeature, parseJsonLines } from './modules/feature-center-bundle';
import type { CanonicalFeatureRecord, FeatureMeshMap } from './modules/feature-center-bundle';
import { buildDetailPanelLayout } from './modules/detail-panel';
import type { DetailGroup } from './modules/detail-panel';
import CadViewerControls from './modules/CadViewerControls.vue';
import type { SceneMode, ToolMode } from './modules/CadViewerControls.vue';
import NativeFeatureTree from './modules/NativeFeatureTree.vue';
import OrientationGizmo from './modules/OrientationGizmo.vue';
import type { GizmoAxisPoint } from './modules/OrientationGizmo.vue';
import { registerCadPickables, resolveCadSelection } from './modules/cad-selection';
import type { CadSelectionTarget } from './modules/cad-selection';
import { buildNativeFeatureTree, flattenFeatureTree } from './modules/native-feature-tree';
import type { FeatureTreeNode, NativeFeatureRecord } from './modules/native-feature-tree';
import {
  clearViewerSelection,
  emptySelectionContext,
  resolveViewerSelection,
  selectionPrimaryId
} from './modules/viewer-selection';
import type {
  SelectionTarget,
  TopologySelectionRecord,
  ViewerSelection,
  ViewerSelectionIndex
} from './modules/viewer-selection';
import {
  readRecentFeatureCenterBuildId,
  resolveFeatureCenterBuildId,
  saveRecentFeatureCenterBuildId
} from './modules/recent-result';
import { defaultBomVisible, isCatiaNativeSource, tabsForSource, workerStageLabel } from './modules/viewer-workspace';
import type { ViewerTab } from './modules/viewer-workspace';

defineOptions({ name: 'FeatureCenterViewer' });

interface MeasurementRecord {
  measurement_id: string;
  feature_center_id: string;
  name: string;
  value: number | null;
  unit: string;
  source: string;
  method: string;
  validity: string;
}

interface BundleManifest {
  schema_version: string;
  brep: { shape_hash: string };
  output_files: Record<string, { sha256: string }>;
}

interface StepCurveRecord {
  id: string;
  name?: string;
  points: number[][];
}

interface StepCurvesAsset {
  schema_version: 'cad_step_curves_v1';
  curve_count: number;
  point_count: number;
  curves: StepCurveRecord[];
}

interface TopologyFaceRecord {
  face_id: string;
  surface_type?: string;
  area?: number;
  centroid?: number[];
  bounding_box?: Record<string, unknown>;
  adjacent_face_ids?: string[];
  boundary_edge_ids?: string[];
  topology_fingerprint?: string;
  kernel_surface_type?: string;
  [key: string]: unknown;
}

interface ProductInstanceRecord {
  instance_id: string;
  parent_instance_id?: string;
  reference_id?: string;
  instance_name?: string;
  instance_path?: string;
  tree_path?: string;
  depth?: number;
  child_index?: number;
  child_count?: number;
  load_status?: string;
  read_status?: string;
  value_source?: string;
  transform_status?: string;
  transform_value_source?: string;
  transform_4x4?: number[];
  suppressed?: boolean;
  [key: string]: unknown;
}

interface FaceMeshMap {
  shape_hash: string;
  faces: Record<string, { mesh_primitive_id: string; primitive_index: number }>;
  primitive_to_face: Record<string, string>;
}

interface ProcessStep {
  sequence: string;
  type: string;
  description: string;
  name?: string;
  specification?: string;
  version?: string;
  category?: string;
  quantity?: string;
  basis?: string;
  remark?: string;
}

// 原型数据来自 AO 工序页，后续可替换为后端解析结果。
const prototypeProcessSteps: ProcessStep[] = [
  {
    sequence: '005',
    type: '铆装钳工',
    name: '聚硫密封剂底涂',
    specification: 'CMS-SL-908',
    category: 'M',
    quantity: '按需',
    description: '按工程数模 5621C02000G23 及 CPS1000、HPGC919-2781-250003，对旅客观察窗窗框与弹簧夹支架贴合面涂覆聚硫密封剂底涂。',
    basis: 'CPS1000、HPGC919-2781-250003',
    remark:
      '按工程数模 5621C02000G23 及 CPS1000、HPGC919-2781-250003，对旅客观察窗窗框与弹簧夹支架贴合面涂覆聚硫密封剂底涂；5621C01005G71 的贴合面涂覆聚硫密封剂，并将参数记录于“非金属材料施工记录表”中。注：涂覆聚硫密封剂前，需要清洗、干燥并使用 CMS-SL-908 聚硫密封剂刷涂底涂；将 CMS-SL-908 聚硫密封剂涂刷在 CPM 6520 搭布上，或倒在待处理的表面上，停留合适的时间后，用搭布单向擦拭，尽可能均匀且厚薄一致地涂覆底胶；在 CMS-SL-908 聚硫密封剂还湿润的时候，用清洁干燥的 CPM 6520 搭布从已经处理的表面上将其擦掉；处理后的表面在施加密封剂前应在室温条件下至少干燥 30 分钟；在处理后的 24 小时内涂密封剂，否则表面需要重新用 CMS-SL-908 聚硫密封剂处理。'
  },
  {
    sequence: '010',
    type: '铆装检验工',
    description: '按 CPS1000 检查聚硫密封剂底涂的涂覆质量。',
    basis: 'CPS1000',
    remark: '按 CPS1000 检查聚硫密封剂底涂的涂覆质量。'
  },
  {
    sequence: '015',
    type: '铆装钳工',
    name: '低密度通用密封化合物',
    specification: 'CMS-SL-104/C-8',
    category: 'M',
    quantity: '按需',
    description: '按工程数模 5621C02000G23 及 CPS1000，对观察窗窗框与弹簧夹支架贴合面涂覆密封胶。',
    basis: '5621C02000G23、CPS1000、HPGC919-2781-250003',
    remark:
      '按工程数模 5621C02000G23、CPS1000、HPGC919-2781-250003，对旅客观察窗窗框与弹簧夹支架贴合面涂覆密封胶；5621C01005G71 的贴合面涂覆密封胶，并将参数记录于“非金属材料施工记录表”中。'
  },
  {
    sequence: '020',
    type: '铆装检验工',
    description: '按 CPS1000 检查密封胶涂覆质量。',
    basis: 'CPS1000',
    remark: '按 CPS1000 检查密封胶涂覆质量。'
  },
  {
    sequence: '025',
    type: '铆装钳工',
    name: '实心铆钉',
    specification: 'MS20470T4-6',
    version: '—',
    category: 'B',
    quantity: '240',
    description: '按工程数模 5621C02000G23、CPS2100 湿安装弹簧夹支架与窗框连接的紧固件，并记录相关工艺参数。',
    basis: '5621C02000G23、CPS2100',
    remark: '按工程数模 5621C02000G23、CPS2100 湿安装弹簧夹支架与窗框连接的紧固件，并将相关工艺参数记录于“非金属材料施工记录表”中。'
  },
  {
    sequence: '030',
    type: '铆装检验工',
    description: '按 CPS2101 检查紧固件安装质量，并记录专用工具与量具信息。',
    basis: 'CPS2101',
    remark: 'MS20470T4* 铆头高度应大于等于 1.58mm、铆头直径应大于等于 3.96mm。'
  },
  {
    sequence: '035',
    type: '铆装钳工',
    description: '按 HPG/MJ-2781-250018 清除多余物。',
    basis: 'HPG/MJ-2781-250018',
    remark: '按 HPG/MJ-2781-250018 清除多余物。'
  }
];

function productInstancesToNativeRecords(records: ProductInstanceRecord[]): NativeFeatureRecord[] {
  return records.map(record => {
    const hasChildren = Number(record.child_count || 0) > 0;
    return {
      feature_id: record.instance_id,
      parent_id: record.parent_instance_id || '',
      traversal_index: Number(record.child_index ?? 0) + Number(record.depth ?? 0) * 100000,
      display_name: record.instance_name || record.instance_path || record.instance_id,
      internal_name: record.instance_path || record.tree_path || record.instance_name || record.instance_id,
      native_type: hasChildren ? 'CATProduct' : 'CATPart',
      startup_type: hasChildren ? 'CATProduct' : 'CATPart',
      container_kind: hasChildren ? 'product' : 'part',
      tree_path: record.tree_path || record.instance_path,
      decode_status: record.read_status,
      decoder_status: record.load_status,
      payload_extraction_status: record.value_source,
      update_status: record.suppressed ? 'suppressed' : 'active',
      attributes: {
        instance_id: record.instance_id,
        parent_instance_id: record.parent_instance_id || '',
        reference_id: record.reference_id || '',
        instance_path: record.instance_path || '',
        tree_path: record.tree_path || '',
        depth: record.depth ?? '',
        child_count: record.child_count ?? 0,
        load_status: record.load_status || '',
        read_status: record.read_status || '',
        value_source: record.value_source || '',
        transform_status: record.transform_status || '',
        transform_value_source: record.transform_value_source || '',
        transform_4x4: record.transform_4x4 || [],
        suppressed: Boolean(record.suppressed)
      },
      raw: record
    };
  });
}

type GeometryCategory = 'body_solid' | 'face' | 'loop' | 'coedge' | 'edge' | 'vertex';

interface GeometryTreeNode {
  id: string;
  label: string;
  subtitle: string;
  kind: SelectionTarget['kind'];
  raw?: TopologyFaceRecord | TopologySelectionRecord;
}

const route = useRoute();
const router = useRouter();
const assetRequestController = new AbortController();
const containerRef = ref<HTMLDivElement | null>(null);
const contract = ref<Api.ComponentBuild.ViewerContract | null>(null);
const canonicalFeatures = ref<CanonicalFeatureRecord[]>([]);
const nativeFeatures = ref<NativeFeatureRecord[]>([]);
const topologyFaces = ref<TopologyFaceRecord[]>([]);
const topologyBodies = ref<TopologySelectionRecord[]>([]);
const topologySolids = ref<TopologySelectionRecord[]>([]);
const topologyLoops = ref<TopologySelectionRecord[]>([]);
const topologyCoedges = ref<TopologySelectionRecord[]>([]);
const topologyEdges = ref<TopologySelectionRecord[]>([]);
const topologyVertices = ref<TopologySelectionRecord[]>([]);
const measurements = ref<MeasurementRecord[]>([]);
const featureMeshMap = ref<FeatureMeshMap | null>(null);
const faceMeshMap = ref<FaceMeshMap | null>(null);
const selectionIndex = ref<ViewerSelectionIndex | null>(null);
const viewerSelection = ref<ViewerSelection>(clearViewerSelection());
const selectedFeatureId = ref('');
const selectedNativeFeatureId = ref('');
// 用途：记录左侧规格树当前行，分组节点也能保留视觉选中状态而不被当成真实 Feature。
const selectedNativeTreeNodeId = ref('');
const selectedFaceId = ref('');
const selectedBomNode = ref<Api.ComponentBuild.ViewerBomNode | null>(null);
const faceFeatureIds = ref<string[]>([]);
const loading = ref(false);
const errorText = ref('');
const explicitError = ref(false);
const detailsOpen = ref(true);
const bomVisible = ref(false);
const activeTab = ref<ViewerTab>('bom');
const featureSubTab = ref<'native' | 'recognized'>('native');
const transparent = ref(false);
const isolated = ref(false);
const sectionEnabled = ref(false);
const sectionOffset = ref(0);
const geometryKeyword = ref('');
const geometryLimit = ref(160);
const geometryCategory = ref<GeometryCategory>('face');
const selectedBomPrimitiveIds = ref<string[]>([]);
const navigationWidth = ref(310);
const toolMode = ref<ToolMode>('select');
const sceneMode = ref<SceneMode>('whole');
const selectionTarget = ref<CadSelectionTarget | null>(null);
const catiaPropertyDialogOpen = ref(false);
const catiaPropertyNode = ref<FeatureTreeNode | null>(null);
const catiaPropertyTab = ref('product');
const processPanelOpen = ref(false);
const processGenerating = ref(false);
const processProgress = ref(0);
const activeProcessSteps = ref<string[]>(['035']);
const explodableGroupCount = ref(0);
const orientationAxes = ref<Record<'x' | 'y' | 'z', GizmoAxisPoint>>({
  x: { x: 66, y: 45, depth: 0 },
  y: { x: 42, y: 21, depth: 0 },
  z: { x: 24, y: 56, depth: 0 }
});

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let modelRoot: THREE.Object3D | null = null;
let stepCurveRoot: THREE.Object3D | null = null;
let animationId = 0;
let resizeObserver: ResizeObserver | null = null;
let statusPollTimer: number | null = null;
let processTimer: number | null = null;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const faceObjects = new Map<string, THREE.Mesh[]>();
const primitiveObjects = new Map<string, THREE.Mesh[]>();
let pickableObjects: THREE.Object3D[] = [];
let pointerDownPosition: { x: number; y: number } | null = null;
const clippingPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
const workspaceStyle = computed(() => ({ '--navigation-width': `${navigationWidth.value}px` }));
const canIsolate = computed(() => {
  if (selectedFaceId.value) return true;
  if (selectedNativeFeatureId.value) return selectedNativeFaces.value.length > 0;
  if (selectedBomNode.value)
    return selectedBomPrimitiveIds.value.length > 0 || contract.value?.bom.assembly_mode === 'single_part';
  return Boolean(featureMeshMap.value && facesForFeature(featureMeshMap.value, selectedFeatureId.value).length);
});
const canExplode = computed(() => contract.value?.bom.assembly_mode === 'assembly' && explodableGroupCount.value > 1);
const selectionContext = computed(() => viewerSelection.value.context || emptySelectionContext());
const primarySelection = computed(() => viewerSelection.value.primary);
const viewerProgress = computed(() => Math.min(100, Math.max(0, Number(contract.value?.progress ?? 0))));
const hasBackendFailure = computed(() =>
  Boolean(contract.value && (contract.value.status === 'failed' || contract.value.error_code || contract.value.error_message))
);
const processingStatusText = computed(() => {
  if (!contract.value || contract.value.status === 'ready') return '';
  return `${isCatiaNativeSource(contract.value.source_format) ? 'CATIA' : '模型'} 处理中：${workerStageLabel(contract.value.current_stage)}`;
});
const showProcessingCard = computed(() =>
  Boolean(contract.value && contract.value.status !== 'ready' && !hasBackendFailure.value && !explicitError.value)
);
const showErrorCard = computed(() => Boolean(errorText.value && explicitError.value));
const recognizedEmptyDescription = computed(() =>
  contract.value && contract.value.status !== 'ready'
    ? '后端仍在处理，识别特征生成后会自动显示'
    : '当前解析结果未提供识别特征索引'
);

// 用途：只展示真实契约中的格式；没有历史结果时保持空值，绝不伪造 CATPart 或 STEP 标签。
const sourceFormat = computed(() => contract.value?.source_format);
const sourceTabs = computed(() => tabsForSource(sourceFormat.value || 'CATPART'));
const selectedFeature = computed(
  () => canonicalFeatures.value.find(item => item.feature_center_id === selectedFeatureId.value) ?? null
);
const selectedNativeFeature = computed(
  () => nativeFeatures.value.find(item => item.feature_id === selectedNativeFeatureId.value) ?? null
);
const selectedFace = computed(() => topologyFaces.value.find(item => item.face_id === selectedFaceId.value) ?? null);
const selectedMeasurements = computed(() =>
  measurements.value.filter(item => item.feature_center_id === selectedFeatureId.value)
);
const nativeFaceRefs = computed(() => {
  const index: Record<string, string[]> = {};
  for (const [featureId, faceIds] of Object.entries(selectionIndex.value?.native_feature_to_native_faces || {})) {
    index[featureId] = [...new Set(faceIds)].sort();
  }
  return index;
});
const nativeTreeNodes = computed(() =>
  buildNativeFeatureTree(nativeFeatures.value, contract.value?.summary.source_file_name || '', nativeFaceRefs.value)
);
const nativeTreeNodeIndex = computed(
  () => new Map(flattenFeatureTree(nativeTreeNodes.value).map(node => [node.id, node]))
);
const selectedNativeTreeNode = computed(() => nativeTreeNodeIndex.value.get(selectedNativeFeatureId.value) ?? null);
const selectedNativeTreeParent = computed(() => {
  const parentId = selectedNativeTreeNode.value?.parentId;
  return parentId ? (nativeTreeNodeIndex.value.get(parentId) ?? null) : null;
});
const selectedNativeParameters = computed(() =>
  Object.entries(
    selectedNativeFeature.value?.native_feature_parameters ||
      selectedNativeFeature.value?.attributes ||
      {}
  )
);
const selectedNativeParameterFamily = computed(() => {
  const payload = selectedNativeFeature.value?.native_feature_parameters as Record<string, unknown> | undefined;
  return String(payload?.family || selectedNativeFeature.value?.payload_type || '');
});
const selectedNativeFaces = computed(() => nativeFaceRefs.value[selectedNativeFeatureId.value] || []);
const filteredFaces = computed(() => {
  const keyword = geometryKeyword.value.trim().toLowerCase();
  const source = keyword
    ? topologyFaces.value.filter(item => `${item.face_id} ${item.surface_type ?? ''}`.toLowerCase().includes(keyword))
    : topologyFaces.value;
  return source.slice(0, geometryLimit.value);
});
const filteredTopologyRecords = computed(() => {
  const keyword = geometryKeyword.value.trim().toLowerCase();
  const source = geometryCategory.value === 'body_solid'
    ? [...topologyBodies.value, ...topologySolids.value]
    : geometryCategory.value === 'loop'
      ? topologyLoops.value
      : geometryCategory.value === 'coedge'
        ? topologyCoedges.value
        : geometryCategory.value === 'edge'
          ? topologyEdges.value
          : geometryCategory.value === 'vertex'
            ? topologyVertices.value
            : [];
  return (keyword
    ? source.filter(item => `${item.id} ${topologyKind(item)}`.toLowerCase().includes(keyword))
    : source).slice(0, geometryLimit.value);
});
const geometryTreeNodes = computed<GeometryTreeNode[]>(() => {
  if (geometryCategory.value === 'face') {
    return filteredFaces.value.map((face, index) => ({
      id: face.face_id,
      label: `面 ${String(index + 1).padStart(3, '0')} · ${faceTypeLabel(face.surface_type)}`,
      subtitle: face.face_id,
      kind: 'face',
      raw: face
    }));
  }
  return filteredTopologyRecords.value.map((record, index) => ({
    id: record.id,
    label: `${topologyKindLabel(topologySelectionKind(record))} ${String(index + 1).padStart(3, '0')}`,
    subtitle: record.id,
    kind: topologySelectionKind(record),
    raw: record
  }));
});
const geometryEmptyDescription = computed(() =>
  geometryCategory.value === 'face'
    ? '当前解析结果未提供 Face 拓扑'
    : `当前解析结果未提供${geometryCategoryLabel(geometryCategory.value)}`
);
const selectedTitle = computed(
  () => {
    const primary = primarySelection.value;
    if (primary?.kind === 'face') return primary.label || primary.id;
    if (primary?.kind === 'native_feature') return selectedNativeFeature.value?.display_name || primary.label || primary.id;
    if (primary?.kind === 'recognized_feature') return selectedFeature.value?.subtype || primary.label || primary.id;
    if (primary && ['assembly', 'part_instance', 'part', 'body', 'solid', 'loop', 'coedge', 'edge', 'vertex'].includes(primary.kind)) {
      return primary.label || primary.id;
    }
    return contract.value?.summary.model_name || '';
  }
);
const mappingAvailable = computed(() => Boolean(contract.value?.summary.feature_face_mapping_available));
const detailNode = computed(() => selectedBomNode.value ?? contract.value?.bom.nodes[0] ?? null);
const detailParentNode = computed(() => {
  const parentId = detailNode.value?.parent_id;
  if (!parentId) return null;
  const pending = [...(contract.value?.bom.nodes ?? [])];
  while (pending.length) {
    const node = pending.shift()!;
    if (node.node_id === parentId) return node;
    pending.push(...node.children);
  }
  return null;
});
const detailLayout = computed(() => {
  if (!contract.value || !sourceFormat.value) {
    return { groups: [] as DetailGroup[], featureLinkLabel: '', featureLinkEnabled: false };
  }
  return buildDetailPanelLayout({
    selectionKind: selectedFace.value
      ? 'geometry'
      : selectedNativeFeature.value || selectedFeature.value
        ? 'feature'
        : 'model',
    assemblyMode: contract.value.bom.assembly_mode,
    nodeType: detailNode.value?.node_type,
    hasParent: Boolean(detailNode.value?.parent_id),
    sourceFormat: sourceFormat.value,
    nativeFeatureAvailable: Boolean(contract.value.native_semantics?.available),
    featureFaceMappingAvailable: mappingAvailable.value,
    geometryHasLinkedFeature: Boolean(selectedFace.value && (selectedNativeFeature.value || selectedFeature.value))
  });
});
const catiaPropertyTitle = computed(() => {
  const node = catiaPropertyNode.value;
  if (!node) return 'CATIA 属性';
  return `${node.displayName}${node.nativeType ? ` · ${node.nativeType}` : ''}`;
});
const catiaPropertyTabs = computed(() => buildCatiaPropertyTabs(catiaPropertyNode.value));

// 用途：模板只查询已计算的业务分组，BOM 的展开或隐藏不会改变右侧属性语义。
function hasDetailGroup(group: DetailGroup) {
  return detailLayout.value.groups.includes(group);
}

// 用途：详情区只格式化真实解析值；对象和数组保留 JSON 结构，不补默认参数。
function formatNativeAttribute(value: unknown) {
  if (value == null) return '未提供';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function nativeAttributesOf(node: FeatureTreeNode | null) {
  return (node?.raw?.attributes || {}) as Record<string, unknown>;
}

function pickAttribute(attrs: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = attrs[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return undefined;
}

function formatCatiaNumber(value: unknown) {
  const numeric = typeof value === 'number' ? value : Number(String(value ?? '').trim());
  if (!Number.isFinite(numeric)) return formatNativeAttribute(value);
  if (numeric === 0) return '0';
  if (Math.abs(numeric) < 0.001) return numeric.toExponential(3);
  const rounded = numeric.toFixed(3);
  return rounded.replace(/\.?0+$/, '');
}

function propertyRow(label: string, value: unknown, unit = '') {
  if (value === undefined || value === null || value === '') return null;
  const text = unit ? formatCatiaNumber(value) : formatNativeAttribute(value);
  return { label, value: unit && !text.endsWith(unit) ? `${text}${unit}` : text };
}

function compactRows(rows: Array<{ label: string; value: string } | null>) {
  return rows.filter(Boolean) as Array<{ label: string; value: string }>;
}

function isCatiaPropertyTarget(node: FeatureTreeNode) {
  const typeText = `${node.kind} ${node.nativeType || ''} ${node.raw?.startup_type || ''} ${node.raw?.native_type || ''}`.toLowerCase();
  return ['catpart', 'catproduct', 'product', 'mechanicalpart', 'part'].some(token => typeText.includes(token));
}

function buildMechanicalRows(node: FeatureTreeNode | null) {
  const attrs = nativeAttributesOf(node);
  return {
    characteristic: compactRows([
      propertyRow('体积', pickAttribute(attrs, ['catia_property_volume_m3', 'volume_m3', 'volume']), 'm3'),
      propertyRow('质量', pickAttribute(attrs, ['catia_property_mass_kg', 'mass_kg', 'mass']), 'kg'),
      propertyRow('曲面', pickAttribute(attrs, ['catia_property_area_m2', 'area_m2', 'surface_area_m2', 'area']), 'm2'),
      propertyRow('密度', pickAttribute(attrs, ['catia_property_density_kg_m3', 'density_kg_m3', 'density']), 'kg_m3')
    ]),
    center: compactRows([
      propertyRow('x', pickAttribute(attrs, ['catia_property_center_x_mm', 'center_x_mm', 'center_x']), 'mm'),
      propertyRow('y', pickAttribute(attrs, ['catia_property_center_y_mm', 'center_y_mm', 'center_y']), 'mm'),
      propertyRow('z', pickAttribute(attrs, ['catia_property_center_z_mm', 'center_z_mm', 'center_z']), 'mm')
    ]),
    inertia: compactRows([
      propertyRow('Ixx', pickAttribute(attrs, ['catia_property_ixx_kg_m2', 'ixx_kg_m2', 'ixx']), 'kgxm2'),
      propertyRow('Ixy', pickAttribute(attrs, ['catia_property_ixy_kg_m2', 'ixy_kg_m2', 'ixy']), 'kgxm2'),
      propertyRow('Ixz', pickAttribute(attrs, ['catia_property_ixz_kg_m2', 'ixz_kg_m2', 'ixz']), 'kgxm2'),
      propertyRow('Iyx', pickAttribute(attrs, ['catia_property_iyx_kg_m2', 'iyx_kg_m2', 'iyx']), 'kgxm2'),
      propertyRow('Iyy', pickAttribute(attrs, ['catia_property_iyy_kg_m2', 'iyy_kg_m2', 'iyy']), 'kgxm2'),
      propertyRow('Iyz', pickAttribute(attrs, ['catia_property_iyz_kg_m2', 'iyz_kg_m2', 'iyz']), 'kgxm2'),
      propertyRow('Izx', pickAttribute(attrs, ['catia_property_izx_kg_m2', 'izx_kg_m2', 'izx']), 'kgxm2'),
      propertyRow('Izy', pickAttribute(attrs, ['catia_property_izy_kg_m2', 'izy_kg_m2', 'izy']), 'kgxm2'),
      propertyRow('Izz', pickAttribute(attrs, ['catia_property_izz_kg_m2', 'izz_kg_m2', 'izz']), 'kgxm2')
    ])
  };
}

function buildCatiaPropertyTabs(node: FeatureTreeNode | null) {
  if (!node) return [];
  const attrs = nativeAttributesOf(node);
  const mechanical = buildMechanicalRows(node);
  const componentRows = compactRows([
    propertyRow('实例名称', pickAttribute(attrs, ['instance_name']) || node.displayName),
    propertyRow('描述', pickAttribute(attrs, ['description'])),
    propertyRow('在物料清单中可视化', pickAttribute(attrs, ['bom_visible', 'visible_in_bom'])),
    propertyRow('StartUp', node.raw?.startup_type || node.nativeType),
    propertyRow('内部名称', node.raw?.internal_name || node.name),
    propertyRow('树路径', node.raw?.tree_path || node.sourceRef)
  ]);
  const referenceRows = compactRows([
    propertyRow('参考链接', pickAttribute(attrs, ['source_document', 'instance_path', 'tree_path']) || node.sourceRef),
    propertyRow('引用 ID', pickAttribute(attrs, ['reference_id'])),
    propertyRow('实例 ID', pickAttribute(attrs, ['instance_id'])),
    propertyRow('父实例 ID', pickAttribute(attrs, ['parent_instance_id']))
  ]);
  const productRows = compactRows([
    propertyRow('零件编号', pickAttribute(attrs, ['part_number']) || node.displayName),
    propertyRow('版本', pickAttribute(attrs, ['revision', 'version'])),
    propertyRow('定义', pickAttribute(attrs, ['definition'])),
    propertyRow('术语', pickAttribute(attrs, ['nomenclature'])),
    propertyRow('源', pickAttribute(attrs, ['source']) || pickAttribute(attrs, ['value_source'])),
    propertyRow('描述', pickAttribute(attrs, ['product_description', 'description'])),
    propertyRow('子节点数', pickAttribute(attrs, ['child_count'])),
    propertyRow('读取状态', pickAttribute(attrs, ['read_status', 'load_status'])),
    propertyRow('更新状态', node.raw?.update_status)
  ]);
  const graphicPropertyRows = compactRows([
    propertyRow('颜色', pickAttribute(attrs, ['color', 'rgb', 'material_color']) || '无颜色'),
    propertyRow('线型', pickAttribute(attrs, ['line_type']) || '无线型'),
    propertyRow('线宽', pickAttribute(attrs, ['line_width']) || '无宽度'),
    propertyRow('透明度', pickAttribute(attrs, ['transparency', 'opacity'])),
    propertyRow('显示状态', pickAttribute(attrs, ['visibility', 'show_status', 'visible']) || node.raw?.visibility)
  ]);
  const graphicGlobalRows = compactRows([
    propertyRow('显示的', pickAttribute(attrs, ['shown', 'visible'])),
    propertyRow('图层', pickAttribute(attrs, ['layer'])),
    propertyRow('渲染样式', pickAttribute(attrs, ['render_style'])),
    propertyRow('可拾取', pickAttribute(attrs, ['pickable'])),
    propertyRow('抑制状态', pickAttribute(attrs, ['suppressed']))
  ]);
  const drawingRows = compactRows([
    propertyRow('工程制图状态', pickAttribute(attrs, ['drafting_status', 'drawing_status'])),
    propertyRow('标注/注释', pickAttribute(attrs, ['annotation_status', 'fta_status'])),
    propertyRow('视图', pickAttribute(attrs, ['drawing_view'])),
    propertyRow('线型继承', pickAttribute(attrs, ['line_inheritance'])),
    propertyRow('TPS/FTA', node.raw?.decoder_id === 'fta' ? node.raw?.decode_status : undefined)
  ]);
  return [
    {
      name: 'product',
      label: '产品',
      groups: [
        { title: '部件', rows: componentRows },
        { title: '参考链接', rows: referenceRows },
        { title: '产品', rows: productRows }
      ]
    },
    {
      name: 'graphic',
      label: '图形',
      groups: [
        { title: '图形属性', rows: graphicPropertyRows },
        { title: '全局属性', rows: graphicGlobalRows }
      ]
    },
    {
      name: 'mechanical',
      label: '机械',
      groups: [
        { title: '特性', rows: mechanical.characteristic },
        { title: '惯性中心', rows: mechanical.center },
        { title: '惯性矩阵', rows: mechanical.inertia }
      ]
    },
    { name: 'drafting', label: '工程制图', groups: [{ title: '工程制图', rows: drawingRows }] }
  ];
}

// 用途：从特征关联面跳到几何拓扑并复用现有 Face 反查与 Viewer 高亮。
function openNativeFace(faceId: string) {
  activeTab.value = 'geometry';
  selectFace(faceId);
}

// 用途：从详情区进入特征列表；只有真实映射能力满足时按钮才会启用。
function openFeatureLinks() {
  if (!detailLayout.value.featureLinkEnabled) return;
  activeTab.value = 'recognized';
  featureSubTab.value = isCatiaNativeSource(sourceFormat.value) ? 'native' : 'recognized';
  bomVisible.value = true;
}

// 用途：桌面端拖动调整左侧规格树宽度，限制在可用范围内并保存本机偏好。
function startNavigationResize(event: PointerEvent) {
  if (!bomVisible.value || window.innerWidth < 900) return;
  const startX = event.clientX;
  const startWidth = navigationWidth.value;
  const move = (moveEvent: PointerEvent) => {
    navigationWidth.value = Math.min(420, Math.max(288, startWidth + moveEvent.clientX - startX));
  };
  const stop = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', stop);
    window.localStorage.setItem('feature-center:navigation-width', String(navigationWidth.value));
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', stop, { once: true });
}

// 用途：从受控资产接口取得字节并校验响应类型，浏览器永远不接触服务器绝对路径。
async function fetchAsset(path: string) {
  const result = await fetchComponentBuildViewerAsset(path, { signal: assetRequestController.signal, silent: true });
  if (result.error || !(result.data instanceof ArrayBuffer)) throw result.error || new Error('Viewer 资产响应无效');
  return result.data;
}

// 用途：加载 STEP/CATPart 共用 Viewer 契约；可选原生语义缺失时不影响真实 GLB 展示。
function clearStatusPoll() {
  if (statusPollTimer == null) return;
  window.clearTimeout(statusPollTimer);
  statusPollTimer = null;
}

function scheduleStatusPoll(buildId: string) {
  clearStatusPoll();
  statusPollTimer = window.setTimeout(() => {
    statusPollTimer = null;
    void loadBuildBundle(buildId);
  }, 1800);
}

async function loadBuildBundle(buildId: string) {
  clearStatusPoll();
  loading.value = true;
  errorText.value = '';
  explicitError.value = false;
  try {
    const result = await fetchComponentBuildViewer(buildId, { signal: assetRequestController.signal, silent: true });
    if (result.error || !result.data) throw result.error || new Error('Viewer 契约不可用');
    if (!isCatiaNativeSource(result.data.source_format)) {
      await router.replace({
        path: '/component-build',
        query: { build_id: buildId, revision_id: result.data.task_id }
      });
      return;
    }
    contract.value = result.data;
    await nextTick();
    if (!renderer) initViewer();
    bomVisible.value = defaultBomVisible(result.data.bom);
    activeTab.value = 'bom';
    if (result.data.status !== 'ready' || !result.data.viewer_asset) {
      if (result.data.status === 'failed' || result.data.error_code || result.data.error_message) {
        explicitError.value = true;
        errorText.value =
          result.data.error_message ||
          result.data.error_code ||
          `${isCatiaNativeSource(result.data.source_format) ? 'CATIA' : '模型'}处理失败`;
      }
      if (!explicitError.value) scheduleStatusPoll(buildId);
      return;
    }

    const viewerAsset = result.data.viewer_asset;
    const canonicalUrl = result.data.feature_center.canonical_features_url;
    const measurementUrl = result.data.feature_center.measurements_url;
    if (!canonicalUrl || !measurementUrl) throw new Error('Feature Center 索引资产缺失');
    const mandatoryBuffers = await Promise.all([
      fetchAsset(viewerAsset.scene_manifest_url),
      fetchAsset(canonicalUrl),
      fetchAsset(measurementUrl),
      fetchAsset(viewerAsset.face_mesh_map_url),
      fetchAsset(viewerAsset.feature_mesh_map_url),
      fetchAsset(viewerAsset.glb_url)
    ]);
    const [manifestBuffer, canonicalBuffer, measurementBuffer, nextFaceMapBuffer, featureMapBuffer, modelBuffer] =
      mandatoryBuffers;
    const decode = (buffer: ArrayBuffer) => new TextDecoder('utf-8').decode(buffer);
    const manifest = JSON.parse(decode(manifestBuffer)) as BundleManifest;
    if (manifest.schema_version !== 'cad_feature_center_v1') throw new Error('Feature Center Schema 不兼容');
    for (const [relativePath, buffer] of [
      ['canonical_features.jsonl', canonicalBuffer],
      ['measurements.jsonl', measurementBuffer],
      ['lightweight/face_mesh_map.json', nextFaceMapBuffer],
      ['lightweight/feature_mesh_map.json', featureMapBuffer],
      ['lightweight/model.glb', modelBuffer]
    ] as const) {
      const expected = manifest.output_files[relativePath]?.sha256;
      if (!expected || (await sha256Buffer(buffer)) !== expected)
        throw new Error(`Bundle 文件哈希不匹配：${relativePath}`);
    }
    const nextFeatureMap = JSON.parse(decode(featureMapBuffer)) as FeatureMeshMap;
    const nextFaceMap = JSON.parse(decode(nextFaceMapBuffer)) as FaceMeshMap;
    if (nextFeatureMap.shape_hash !== manifest.brep.shape_hash || nextFaceMap.shape_hash !== manifest.brep.shape_hash) {
      throw new Error('Mesh 映射与 B-Rep Shape Hash 不一致');
    }

    canonicalFeatures.value = parseJsonLines<CanonicalFeatureRecord>(decode(canonicalBuffer));
    measurements.value = parseJsonLines<MeasurementRecord>(decode(measurementBuffer));
    featureMeshMap.value = nextFeatureMap;
    faceMeshMap.value = nextFaceMap;
    await loadGlb(modelBuffer);
    await loadStepCurves(viewerAsset.curves_url, manifest);
    await loadOptionalSemanticAssets(result.data);
    clearSelection();
    saveRecentFeatureCenterBuildId(window.localStorage, buildId);
  } catch (error) {
    explicitError.value = true;
    errorText.value = error instanceof Error ? error.message : 'Web Viewer 加载失败';
  } finally {
    loading.value = false;
  }
}

// 用途：复用已保存源文件重新排队，不要求用户再次上传 CATPart/STEP。
async function retryBuild() {
  const buildId = typeof route.query.build_id === 'string' ? route.query.build_id : '';
  if (!buildId) return;
  loading.value = true;
  const result = await retryComponentBuild(buildId, 'reference_step');
  if (result.error) {
    explicitError.value = true;
    errorText.value = result.error instanceof Error ? result.error.message : '重试提交失败';
  } else {
    explicitError.value = false;
    errorText.value = '';
    window.setTimeout(() => void loadBuildBundle(buildId), 800);
  }
  loading.value = false;
}

// 用途：并行读取原生 CAA Feature 与 B-Rep Face；缺失代表数据能力降级，不伪造内容。
async function loadOptionalSemanticAssets(viewerContract: Api.ComponentBuild.ViewerContract) {
  nativeFeatures.value = [];
  topologyFaces.value = [];
  topologyBodies.value = [];
  topologySolids.value = [];
  topologyLoops.value = [];
  topologyCoedges.value = [];
  topologyEdges.value = [];
  topologyVertices.value = [];
  selectionIndex.value = null;
  const productFeatureTreeUrl = viewerContract.native_semantics?.product_feature_tree_url;
  const productInstancesUrl = viewerContract.native_semantics?.product_instances_url;
  const nativeUrl = viewerContract.native_semantics?.features_url;
  const shouldLoadProductTree = viewerContract.source_format === 'CATPRODUCT';
  const facesUrl = viewerContract.feature_center.topology_faces_url;
  const selectionIndexUrl = viewerContract.viewer_asset?.selection_index_url;
  const requests: Promise<void>[] = [];
  if (selectionIndexUrl) {
    requests.push(
      fetchAsset(selectionIndexUrl).then(buffer => {
        const loaded = JSON.parse(new TextDecoder().decode(buffer)) as ViewerSelectionIndex;
        selectionIndex.value = {
          ...loaded,
          native_feature_to_native_faces: {
            ...(loaded.native_feature_to_native_faces || {}),
            ...(selectionIndex.value?.native_feature_to_native_faces || {})
          }
        };
        hydrateTopologyFromSelectionIndex(selectionIndex.value);
      })
    );
  }
  if (shouldLoadProductTree && productFeatureTreeUrl) {
    requests.push(
      fetchAsset(productFeatureTreeUrl).then(buffer => {
        nativeFeatures.value = parseJsonLines<NativeFeatureRecord>(new TextDecoder().decode(buffer));
      })
    );
  } else if (shouldLoadProductTree && productInstancesUrl) {
    requests.push(
      fetchAsset(productInstancesUrl).then(buffer => {
        nativeFeatures.value = productInstancesToNativeRecords(
          parseJsonLines<ProductInstanceRecord>(new TextDecoder().decode(buffer))
        );
      })
    );
  } else if (nativeUrl) {
    requests.push(
      fetchAsset(nativeUrl).then(buffer => {
        nativeFeatures.value = parseJsonLines<NativeFeatureRecord>(new TextDecoder().decode(buffer));
      })
    );
  }
  if (facesUrl) {
    requests.push(
      fetchAsset(facesUrl).then(buffer => {
        topologyFaces.value = parseJsonLines<TopologyFaceRecord>(new TextDecoder().decode(buffer));
      })
    );
  }
  for (const [url, assign] of [
    [viewerContract.native_semantics?.topology_bodies_url, (records: TopologySelectionRecord[]) => (topologyBodies.value = records)],
    [viewerContract.native_semantics?.topology_cells_url, hydrateNativeCells],
    [viewerContract.native_semantics?.topology_wires_url, (records: TopologySelectionRecord[]) => (topologyLoops.value = records)],
    [viewerContract.native_semantics?.topology_coedges_url, (records: TopologySelectionRecord[]) => (topologyCoedges.value = records)]
  ] as const) {
    if (!url) continue;
    requests.push(
      fetchAsset(url).then(buffer => {
        assign(parseJsonLines<TopologySelectionRecord>(new TextDecoder().decode(buffer)));
      })
    );
  }
  if (viewerContract.native_semantics?.feature_topology_links_url) {
    requests.push(
      fetchAsset(viewerContract.native_semantics.feature_topology_links_url).then(buffer => {
        mergeNativeFeatureTopologyLinks(parseJsonLines<Record<string, unknown>>(new TextDecoder().decode(buffer)));
      })
    );
  }
  await Promise.all(requests);
}

function hydrateTopologyFromSelectionIndex(index: ViewerSelectionIndex | null) {
  topologyBodies.value = Object.values(index?.topology?.bodies || {});
  topologySolids.value = Object.values(index?.topology?.solids || {});
  topologyLoops.value = [
    ...Object.values(index?.topology?.loops || {}),
    ...Object.values(index?.topology?.wires || {})
  ];
  topologyCoedges.value = Object.values(index?.topology?.coedges || {});
  topologyEdges.value = Object.values(index?.topology?.edges || {});
  topologyVertices.value = Object.values(index?.topology?.vertices || {});
}

function hydrateNativeCells(records: TopologySelectionRecord[]) {
  const cells = records.map(record => normalizeTopologyRecord(record));
  topologyFaces.value = topologyFaces.value.length
    ? topologyFaces.value
    : cells
      .filter(record => topologyKind(record) === 'face')
      .map(record => ({
        ...(record.raw || {}),
        face_id: record.id,
        surface_type: String((record.raw || {}).surface_type || (record.raw || {}).kernel_surface_type || '')
      }));
  topologySolids.value = [...topologySolids.value, ...cells.filter(record => topologyKind(record) === 'solid')];
  topologyEdges.value = [...topologyEdges.value, ...cells.filter(record => topologyKind(record) === 'edge')];
  topologyVertices.value = [...topologyVertices.value, ...cells.filter(record => topologyKind(record) === 'vertex')];
}

function normalizeTopologyRecord(record: TopologySelectionRecord): TopologySelectionRecord {
  const raw = (record.raw || record) as Record<string, unknown>;
  return {
    ...record,
    id: String(record.id || raw.entity_id || raw.cell_id || raw.id || ''),
    parent_id: String(record.parent_id || raw.parent_id || raw.parent_entity_id || ''),
    owning_body_id: String(record.owning_body_id || raw.owning_body_id || raw.body_id || ''),
    raw
  };
}

function topologyKind(record: TopologySelectionRecord) {
  const raw = (record.raw || {}) as Record<string, unknown>;
  return String(raw.topology_type || raw.entity_type || raw.cell_type || raw.type || '').toLowerCase();
}

function mergeNativeFeatureTopologyLinks(records: Array<Record<string, unknown>>) {
  const nextIndex: ViewerSelectionIndex = selectionIndex.value || {
    schema_version: 'cad_viewer_selection_v1',
    native_feature_to_native_faces: {}
  };
  const featureToFaces = { ...(nextIndex.native_feature_to_native_faces || {}) };
  for (const record of records) {
    const featureId = String(record.source_feature_id || record.feature_id || record.native_feature_id || '');
    const faceId = String(record.final_cell_id || record.target_cell_id || record.face_id || record.native_face_id || '');
    const status = String(record.mapping_status || '').toLowerCase();
    if (!featureId || !faceId) continue;
    if (status && !['runtime_matched', 'runtime_current_revision', 'survives_to_final', 'exact'].includes(status)) continue;
    featureToFaces[featureId] = [...new Set([...(featureToFaces[featureId] || []), faceId])].sort();
  }
  selectionIndex.value = { ...nextIndex, native_feature_to_native_faces: featureToFaces };
}

// 用途：载入一次真实 GLB；BOM/详情栏显隐只触发 ResizeObserver，不重新调用本函数。
async function loadGlb(buffer: ArrayBuffer) {
  if (!scene) throw new Error('Viewer 尚未初始化');
  const gltf = await new Promise<Awaited<ReturnType<GLTFLoader['parseAsync']>>>((resolve, reject) => {
    new GLTFLoader().parse(buffer, '', resolve, reject);
  });
  clearStepCurves();
  if (modelRoot) scene.remove(modelRoot);
  disposeModel(modelRoot);
  faceObjects.clear();
  primitiveObjects.clear();
  pickableObjects = [];
  explodableGroupCount.value = 0;
  modelRoot = gltf.scene;
  modelRoot.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    if (!object.geometry.getAttribute('normal')) object.geometry.computeVertexNormals();
    const original = object.material;
    object.material = Array.isArray(original) ? original.map(item => item.clone()) : original.clone();
    object.userData.cad_original_visible = object.visible;
    object.userData.cad_original_position = object.position.clone();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(material => rememberMaterial(material));
  });
  const registration = registerCadPickables(modelRoot, faceMeshMap.value);
  pickableObjects = registration.pickables;
  registration.faceObjects.forEach((objects, id) => faceObjects.set(id, objects));
  registration.primitiveObjects.forEach((objects, id) => primitiveObjects.set(id, objects));
  explodableGroupCount.value = countExplodableGroups();
  scene.add(modelRoot);
  applyToolMode();
  fitCamera();
}

async function loadStepCurves(curvesUrl: string | null | undefined, manifest: BundleManifest) {
  clearStepCurves();
  if (!scene || !curvesUrl) return;
  const buffer = await fetchAsset(curvesUrl);
  const expected = manifest.output_files['lightweight/curves.json']?.sha256;
  if (expected && (await sha256Buffer(buffer)) !== expected) throw new Error('Bundle 文件哈希不匹配：lightweight/curves.json');
  const asset = JSON.parse(new TextDecoder('utf-8').decode(buffer)) as StepCurvesAsset;
  if (asset.schema_version !== 'cad_step_curves_v1' || !asset.curves.length) return;

  const root = new THREE.Group();
  root.name = 'STEP 曲线';
  const colorA = new THREE.Color('#00d4ff');
  const colorB = new THREE.Color('#f8e71c');
  for (let index = 0; index < asset.curves.length; index += 1) {
    const curve = asset.curves[index];
    if (!Array.isArray(curve.points) || curve.points.length < 2) continue;
    const positions: number[] = [];
    for (let pointIndex = 1; pointIndex < curve.points.length; pointIndex += 1) {
      const previous = curve.points[pointIndex - 1];
      const current = curve.points[pointIndex];
      if (previous.length < 3 || current.length < 3) continue;
      positions.push(previous[0], previous[1], previous[2], current[0], current[1], current[2]);
    }
    if (!positions.length) continue;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const material = new THREE.LineBasicMaterial({
      color: (index % 2 ? colorA : colorB).clone(),
      linewidth: 1.5,
      transparent: true,
      opacity: 0.95,
      depthTest: true,
    });
    const line = new THREE.LineSegments(geometry, material);
    line.name = curve.name || curve.id;
    line.userData.step_curve_id = curve.id;
    root.add(line);
  }
  if (!root.children.length) return;
  stepCurveRoot = root;
  scene.add(root);
  fitCamera();
}

function clearStepCurves() {
  if (scene && stepCurveRoot) scene.remove(stepCurveRoot);
  disposeModel(stepCurveRoot);
  stepCurveRoot = null;
}

function selectTarget(target: SelectionTarget, origin: SelectionTarget['source']) {
  viewerSelection.value = resolveViewerSelection(
    { ...target, source: origin },
    {
      selectionIndex: selectionIndex.value,
      faceMeshMap: faceMeshMap.value,
      featureMeshMap: featureMeshMap.value,
      bomNodes: contract.value?.bom.nodes || [],
      canonicalFeatures: canonicalFeatures.value,
      nativeFeatures: nativeFeatures.value
    }
  );
  projectSelectionForExistingTemplate();
  applyVisualState();
}

function projectSelectionForExistingTemplate() {
  const primary = viewerSelection.value.primary;
  const context = viewerSelection.value.context;
  selectedFeatureId.value = primary?.kind === 'recognized_feature'
    ? primary.id
    : context.recognizedFeatureIds[0] || '';
  selectedNativeFeatureId.value = primary?.kind === 'native_feature'
    ? primary.id
    : context.nativeFeatureIds[0] || '';
  selectedFaceId.value = primary?.kind === 'face'
    ? primary.id
    : context.renderFaceIds[0] || '';
  selectedBomNode.value =
    primary && ['assembly', 'part_instance', 'part'].includes(primary.kind)
      ? findBomNode(contract.value?.bom.nodes || [], primary.id)
      : context.bomNodeIds[0]
        ? findBomNode(contract.value?.bom.nodes || [], context.bomNodeIds[0])
        : null;
  selectedBomPrimitiveIds.value = [...context.primitiveIds];
  faceFeatureIds.value = [...context.recognizedFeatureIds];
}

function findBomNode(nodes: Api.ComponentBuild.ViewerBomNode[], nodeId: string): Api.ComponentBuild.ViewerBomNode | null {
  for (const node of nodes) {
    if (node.node_id === nodeId) return node;
    const child = findBomNode(node.children || [], nodeId);
    if (child) return child;
  }
  return null;
}

// 用途：清除语义选择但保持相机、透明、隔离和剖切状态。
function clearSelection() {
  viewerSelection.value = clearViewerSelection();
  selectedFeatureId.value = '';
  selectedNativeFeatureId.value = '';
  selectedNativeTreeNodeId.value = '';
  selectedFaceId.value = '';
  selectedBomNode.value = null;
  selectedBomPrimitiveIds.value = [];
  faceFeatureIds.value = [];
  selectionTarget.value = null;
  if (isolated.value) isolated.value = false;
  applyVisualState();
}

// 用途：选择 Canonical Feature 后通过 feature_mesh_map 高亮真实面。
function selectFeature(featureId: string) {
  const feature = canonicalFeatures.value.find(item => item.feature_center_id === featureId);
  selectionTarget.value = {
    source: 'catia',
    kind: 'feature',
    stableId: featureId,
    featureId,
    partId: contract.value?.part_id,
    displayName: feature?.subtype
  };
  selectTarget({ kind: 'recognized_feature', id: featureId, label: feature?.subtype, raw: feature }, 'recognized_feature');
}

// 用途：把 CAA 原生 Feature 关联到引用它的 Canonical Feature；无映射时如实保留选择。
function selectNativeFeature(feature: NativeFeatureRecord) {
  selectedNativeTreeNodeId.value = feature.feature_id;
  selectionTarget.value = {
    source: 'catia',
    kind: 'feature',
    stableId: feature.feature_id,
    featureId: feature.feature_id,
    partId: contract.value?.part_id,
    displayName: feature.display_name,
    sourceRef: feature.tree_path,
    raw: feature
  };
  selectTarget({ kind: 'native_feature', id: feature.feature_id, label: feature.display_name, raw: feature }, 'native_feature');
}

// 用途：规格树分组节点只参与导航；真实 Feature 节点继续复用原有选择和关联面高亮链路。
function selectNativeTreeNode(node: FeatureTreeNode) {
  selectedNativeTreeNodeId.value = node.id;
  if (node.raw) {
    selectNativeFeature(node.raw);
    return;
  }
  viewerSelection.value = clearViewerSelection();
  projectSelectionForExistingTemplate();
  selectionTarget.value = null;
  applyVisualState();
}

// 用途：选择真实 BOM 节点并使用后端提供的 Primitive 映射；单零件根节点可代表完整模型。
function showNativeTreeNodeProperties(node: FeatureTreeNode) {
  selectNativeTreeNode(node);
  if (!isCatiaPropertyTarget(node)) return;
  catiaPropertyNode.value = node;
  catiaPropertyTab.value = buildMechanicalRows(node).characteristic.length ? 'mechanical' : 'product';
  catiaPropertyDialogOpen.value = true;
}

function selectBom(node: Api.ComponentBuild.ViewerBomNode) {
  selectedNativeTreeNodeId.value = '';
  selectionTarget.value = {
    source: 'catia',
    kind: node.node_type === 'assembly' || node.node_type === 'subassembly' ? 'assembly' : 'part',
    stableId: node.node_id,
    assemblyId: node.node_type === 'assembly' || node.node_type === 'subassembly' ? node.node_id : undefined,
    instanceId: node.instance_name || undefined,
    partId: node.node_type === 'part' ? node.node_id : contract.value?.part_id,
    displayName: node.name,
    sourceRef: node.assembly_path,
    raw: node
  };
  const kind = node.node_type === 'assembly' || node.node_type === 'subassembly'
    ? 'assembly'
    : node.node_type === 'part' || node.node_type === 'imported_object'
      ? 'part_instance'
      : node.node_type === 'body'
        ? 'body'
        : node.node_type === 'solid'
          ? 'solid'
          : 'part';
  selectTarget({ kind, id: node.node_id, label: node.name, instancePath: node.assembly_path, raw: node }, 'bom');
}

// 用途：选择拓扑 Face 后同步反查关联 Feature，并滚动语义页签。
function selectFace(faceId: string) {
  const rawFace = topologyFaces.value.find(item => item.face_id === faceId);
  selectionTarget.value = {
    source: 'catia',
    kind: 'face',
    stableId: faceId,
    faceId,
    partId: contract.value?.part_id,
    raw: rawFace
  };
  selectTarget({ kind: 'face', id: faceId, label: faceId, raw: rawFace }, 'topology');
}

function selectTopology(kind: SelectionTarget['kind'], record: TopologySelectionRecord) {
  selectTarget({ kind, id: record.id, label: record.id, raw: record.raw || record }, 'topology');
}

function selectGeometryTreeNode(node: GeometryTreeNode) {
  if (node.kind === 'face') {
    selectFace(node.id);
    return;
  }
  selectTopology(node.kind, node.raw as TopologySelectionRecord);
}

function topologySelectionKind(record: TopologySelectionRecord): SelectionTarget['kind'] {
  if (geometryCategory.value === 'body_solid') return topologyKind(record) === 'body' ? 'body' : 'solid';
  if (geometryCategory.value === 'loop') return 'loop';
  if (geometryCategory.value === 'coedge') return 'coedge';
  if (geometryCategory.value === 'edge') return 'edge';
  if (geometryCategory.value === 'vertex') return 'vertex';
  return 'face';
}

function setGeometryCategory(command: string | number | object) {
  const value = String(command) as GeometryCategory;
  if (['body_solid', 'face', 'loop', 'coedge', 'edge', 'vertex'].includes(value)) {
    geometryCategory.value = value;
  }
}

interface MaterialSnapshot {
  color?: number;
  emissive?: number;
  emissiveIntensity?: number;
  transparent: boolean;
  opacity: number;
  depthWrite: boolean;
}

// 用途：保存每个克隆材质的原始外观，关闭透明或高亮后能够完整恢复而不污染共享材质。
function rememberMaterial(material: THREE.Material) {
  const standard = material as THREE.MeshStandardMaterial;
  const snapshot: MaterialSnapshot = {
    color: standard.color?.getHex(),
    emissive: standard.emissive?.getHex(),
    emissiveIntensity: standard.emissiveIntensity,
    transparent: material.transparent,
    opacity: material.opacity,
    depthWrite: material.depthWrite
  };
  material.userData.cad_original_material = snapshot;
}

// 用途：恢复材质的颜色、发光、透明度和深度写入，避免多次切换模式后累积视觉误差。
function restoreMaterial(material: THREE.Material) {
  const snapshot = material.userData.cad_original_material as MaterialSnapshot | undefined;
  if (!snapshot) return;
  const standard = material as THREE.MeshStandardMaterial;
  if (snapshot.color != null && standard.color) standard.color.setHex(snapshot.color);
  if (snapshot.emissive != null && standard.emissive) standard.emissive.setHex(snapshot.emissive);
  if (snapshot.emissiveIntensity != null) standard.emissiveIntensity = snapshot.emissiveIntensity;
  material.transparent = snapshot.transparent;
  material.opacity = snapshot.opacity;
  material.depthWrite = snapshot.depthWrite;
}

// 用途：统一计算选中、高亮、隔离、透明和剖切，不因侧栏响应式变化重置模型状态。
function applyVisualState() {
  const context = selectionContext.value;
  const featureFaces = new Set([
    ...(featureMeshMap.value ? facesForFeature(featureMeshMap.value, selectedFeatureId.value) : []),
    ...selectedNativeFaces.value,
    ...context.renderFaceIds,
    ...context.nativeFaceIds
  ]);
  const bomPrimitives = new Set([...selectedBomPrimitiveIds.value, ...context.primitiveIds]);
  const wholeSinglePart = Boolean(selectedBomNode.value && contract.value?.bom.assembly_mode === 'single_part');
  const hasSelection =
    featureFaces.size > 0 || bomPrimitives.size > 0 || wholeSinglePart || Boolean(selectedFaceId.value);
  for (const object of pickableObjects) {
    if (!(object instanceof THREE.Mesh)) continue;
    const primitiveId = String(object.userData.mesh_primitive_id ?? object.userData.primitive_id ?? '');
    const faceId = String(
      object.userData.face_id ??
        object.userData.cad_face_id ??
        (primitiveId ? faceMeshMap.value?.primitive_to_face?.[primitiveId] : '') ??
        ''
    );
    const active =
      wholeSinglePart ||
      featureFaces.has(faceId) ||
      faceId === selectedFaceId.value ||
      bomPrimitives.has(primitiveId);
    const originalVisible = object.userData.cad_original_visible !== false;
    object.visible = originalVisible && (!isolated.value || !hasSelection || active);
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      const standard = material as THREE.MeshStandardMaterial;
      restoreMaterial(material);
      if (hasSelection && active) {
        standard.color?.set('#6254d8');
        standard.emissive?.set('#6254d8');
        standard.emissiveIntensity = 0.35;
      }
      if (transparent.value) {
        standard.transparent = true;
        standard.opacity = hasSelection && active ? 0.94 : 0.2;
        standard.depthWrite = Boolean(hasSelection && active);
      }
      standard.clippingPlanes = sectionEnabled.value ? [clippingPlane] : [];
      standard.needsUpdate = true;
    }
  }
  clippingPlane.constant = sectionOffset.value;
}

// 用途：记录按下位置，供抬起时区分真实单击与旋转、平移拖动。
function handlePointerDown(event: PointerEvent) {
  pointerDownPosition = { x: event.clientX, y: event.clientY };
}

// 用途：选择模式下从真实 GLB extras/映射表解析 Face；没有 Face 元数据时只降级选择零件。
function handlePointerUp(event: PointerEvent) {
  if (!renderer || !camera || toolMode.value !== 'select') return;
  const down = pointerDownPosition;
  pointerDownPosition = null;
  if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 4) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster
    .intersectObjects(pickableObjects, false)
    .find(item => item.object.visible && item.object.userData.pickable !== false);
  if (!hit) {
    clearSelection();
    return;
  }
  const target = resolveCadSelection(hit, 'catia', faceMeshMap.value, {
    partId: contract.value?.part_id || 'CATPART',
    displayName: contract.value?.summary.model_name,
    sourceRef: contract.value?.summary.source_file_name || undefined
  });
  if (target.kind === 'face' && target.faceId) {
    selectTarget({ kind: 'face', id: target.faceId, label: target.faceId, raw: target.raw }, 'canvas');
    selectionTarget.value = target;
    return;
  }
  const root = contract.value?.bom.nodes[0];
  if (root) selectBom(root);
  else selectionTarget.value = target;
}

// 用途：建立共享渲染环境；STEP 和 CATPart 只更换数据适配器，不创建第二套 Viewer。
function initViewer() {
  const container = containerRef.value;
  if (!container || scene) return;
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#f7f8fb');
  camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1_000_000);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.localClippingEnabled = true;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.addEventListener('change', updateOrientationAxes);
  scene.add(new THREE.HemisphereLight('#ffffff', '#64748b', 1.25));
  const light = new THREE.DirectionalLight('#ffffff', 1.8);
  light.position.set(1, 1, 2);
  scene.add(light);
  renderer.domElement.addEventListener('pointerdown', handlePointerDown);
  renderer.domElement.addEventListener('pointerup', handlePointerUp);
  resizeObserver = new ResizeObserver(resizeViewer);
  resizeObserver.observe(container);
  resizeViewer();
  animate();
}

// 用途：同步选择、旋转和平移三种鼠标语义，三个模式均保留滚轮缩放。
function applyToolMode() {
  if (!controls || !renderer) return;
  controls.enableRotate = toolMode.value === 'orbit';
  controls.enablePan = toolMode.value === 'pan';
  controls.mouseButtons.LEFT =
    toolMode.value === 'orbit' ? THREE.MOUSE.ROTATE : toolMode.value === 'pan' ? THREE.MOUSE.PAN : null;
  renderer.domElement.style.cursor = toolMode.value === 'select' ? 'default' : 'grab';
}

// 用途：把相机四元数投影到屏幕坐标，坐标轴固定在左下角但随相机方向实时转动。
function updateOrientationAxes() {
  if (!camera) return;
  const inverse = camera.quaternion.clone().invert();
  const project = (axis: THREE.Vector3): GizmoAxisPoint => {
    const view = axis.applyQuaternion(inverse);
    return { x: 42 + view.x * 24, y: 45 - view.y * 24, depth: view.z };
  };
  orientationAxes.value = {
    x: project(new THREE.Vector3(1, 0, 0)),
    y: project(new THREE.Vector3(0, 1, 0)),
    z: project(new THREE.Vector3(0, 0, 1))
  };
}

// 用途：按真实模型包围盒适应窗口，不写死参考图尺寸或相机位置。
function fitCamera() {
  if (!camera || !controls) return;
  const roots = [modelRoot, stepCurveRoot].filter((item): item is THREE.Object3D => Boolean(item));
  if (!roots.length) return;
  const box = new THREE.Box3();
  for (const root of roots) {
    const nextBox = new THREE.Box3().setFromObject(root);
    if (!Number.isFinite(nextBox.min.x) || !Number.isFinite(nextBox.max.x)) continue;
    if (nextBox.isEmpty()) continue;
    box.union(nextBox);
  }
  if (!Number.isFinite(box.min.x) || box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const distance = Math.max(size.x, size.y, size.z, 1) * 1.8;
  camera.position.copy(center.clone().add(new THREE.Vector3(distance, distance, distance)));
  camera.near = Math.max(distance / 10_000, 0.001);
  camera.far = distance * 30;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
  updateOrientationAxes();
}

// 用途：点击坐标轴后保持当前观察距离并切换到正 X/Y/Z 标准视图。
function snapCamera(axis: 'x' | 'y' | 'z') {
  if (!camera || !controls) return;
  const distance = Math.max(camera.position.distanceTo(controls.target), 1);
  const direction =
    axis === 'x' ? new THREE.Vector3(1, 0, 0) : axis === 'y' ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, 1);
  camera.position.copy(controls.target.clone().add(direction.multiplyScalar(distance)));
  camera.up.set(0, axis === 'y' ? 0 : 1, axis === 'y' ? 1 : 0);
  camera.lookAt(controls.target);
  controls.update();
  updateOrientationAxes();
}

// 用途：统计具有真实 Primitive 归属的装配实例；不足两个实例时禁用爆炸，避免单零件伪动画。
function countExplodableGroups() {
  if (contract.value?.bom.assembly_mode !== 'assembly') return 0;
  const groups = new Set<string>();
  const visit = (node: Api.ComponentBuild.ViewerBomNode) => {
    if (node.mesh_primitive_ids.some(id => primitiveObjects.has(id))) groups.add(node.node_id);
    node.children.forEach(visit);
  };
  contract.value.bom.nodes.forEach(visit);
  return groups.size;
}

// 用途：从原始坐标计算装配爆炸位移，始终基于备份位置写入，因此重复切换不会累计漂移。
function applyExplodedState(enabled: boolean) {
  if (!modelRoot) return;
  const wholeBox = new THREE.Box3().setFromObject(modelRoot);
  const wholeCenter = wholeBox.getCenter(new THREE.Vector3());
  const scale = Math.max(wholeBox.getSize(new THREE.Vector3()).length() * 0.12, 1);
  const moved = new Set<THREE.Mesh>();
  const visit = (node: Api.ComponentBuild.ViewerBomNode) => {
    const objects = [...new Set(node.mesh_primitive_ids.flatMap(id => primitiveObjects.get(id) || []))].filter(
      item => !moved.has(item)
    );
    if (objects.length) {
      const center = new THREE.Box3().setFromObject(objects[0]);
      objects.slice(1).forEach(object => center.expandByObject(object));
      const direction = center.getCenter(new THREE.Vector3()).sub(wholeCenter);
      if (direction.lengthSq() > 1e-9) direction.normalize();
      objects.forEach(object => {
        const original = object.userData.cad_original_position as THREE.Vector3 | undefined;
        if (original)
          object.position.copy(original).add(enabled ? direction.clone().multiplyScalar(scale) : new THREE.Vector3());
        moved.add(object);
      });
    }
    node.children.forEach(visit);
  };
  contract.value?.bom.nodes.forEach(visit);
  if (!enabled) {
    modelRoot.traverse(object => {
      if (!(object instanceof THREE.Mesh) || moved.has(object)) return;
      const original = object.userData.cad_original_position as THREE.Vector3 | undefined;
      if (original) object.position.copy(original);
    });
  }
}

// 用途：场景分段控制统一修改真实 Viewer 状态；“整体”恢复可见性、材质、剖切和相机。
function setSceneMode(mode: SceneMode) {
  if (mode === 'explode' && !canExplode.value) return;
  sceneMode.value = mode;
  if (mode === 'whole') {
    transparent.value = false;
    isolated.value = false;
    sectionEnabled.value = false;
    applyExplodedState(false);
    fitCamera();
  } else if (mode === 'explode') {
    applyExplodedState(true);
  } else if (mode === 'transparent') {
    applyExplodedState(false);
    transparent.value = true;
  } else {
    applyExplodedState(false);
    sectionEnabled.value = true;
  }
  applyVisualState();
}

// 用途：透明开关直接控制材质，同时让分段模式与真实场景状态一致。
function setTransparent(value: boolean) {
  transparent.value = value;
  if (value) sceneMode.value = 'transparent';
  else if (sceneMode.value === 'transparent') sceneMode.value = 'whole';
  applyVisualState();
}

// 用途：隔离开关只在存在可定位选择时生效，关闭后按每个 Mesh 的原始可见性恢复。
function setIsolated(value: boolean) {
  isolated.value = value && canIsolate.value;
  applyVisualState();
}

// 用途：剖切开关控制真实 clipping plane，并同步场景分段状态。
function setSectionEnabled(value: boolean) {
  sectionEnabled.value = value;
  if (value) sceneMode.value = 'section';
  else if (sceneMode.value === 'section') sceneMode.value = 'whole';
  applyVisualState();
}

// 用途：图层按钮打开现有 BOM/可见性入口，不创建没有功能的空面板。
function openLayers() {
  activeTab.value = 'bom';
  if (!bomVisible.value) toggleBom();
}

// 用途：侧栏显隐和断点变化后立即更新 WebGL 像素尺寸与相机宽高比。
function resizeViewer() {
  if (!containerRef.value || !renderer || !camera) return;
  const width = Math.max(containerRef.value.clientWidth, 1);
  const height = Math.max(containerRef.value.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  if (!renderer || !scene || !camera) return;
  controls?.update();
  renderer.render(scene, camera);
  animationId = requestAnimationFrame(animate);
}

// 用途：释放模型显存，避免路由切换或重载 Bundle 后遗留 GPU 资源。
function disposeModel(root: THREE.Object3D | null) {
  root?.traverse(object => {
    if (!(object instanceof THREE.Mesh) && !(object instanceof THREE.LineSegments)) return;
    object.geometry.dispose();
    const material = object.material as THREE.Material | THREE.Material[];
    const materials = Array.isArray(material) ? material : [material];
    materials.forEach(item => item.dispose());
  });
}

function toggleBom() {
  bomVisible.value = !bomVisible.value;
  void nextTick(resizeViewer);
}

function toggleDetails() {
  detailsOpen.value = !detailsOpen.value;
  void nextTick(resizeViewer);
}

function openProcessPanel() {
  processPanelOpen.value = true;
  processGenerating.value = true;
  processProgress.value = 0;
  if (processTimer) window.clearInterval(processTimer);
  processTimer = window.setInterval(() => {
    processProgress.value = Math.min(100, processProgress.value + 10);
    if (processProgress.value >= 100) {
      processGenerating.value = false;
      if (processTimer) window.clearInterval(processTimer);
      processTimer = null;
    }
  }, 120);
}

function closeProcessPanel() {
  processPanelOpen.value = false;
}

function showProcessStep(sequence: string) {
  if (!activeProcessSteps.value.includes(sequence)) activeProcessSteps.value.push(sequence);
}

function tabLabel(tab: ViewerTab) {
  return { bom: 'BOM 树', native: '原生特征', recognized: '特征', geometry: '几何拓扑' }[tab];
}

function faceTypeLabel(type: string | undefined) {
  return (
    (
      {
        plane: '平面',
        cylinder: '圆柱面',
        cone: '圆锥面',
        sphere: '球面',
        torus: '圆环面',
        bspline: 'B 样条面',
        bezier: 'Bezier 面'
      } as Record<string, string>
    )[type ?? ''] ??
    type ??
    '其他曲面'
  );
}

function geometryCategoryLabel(category: GeometryCategory) {
  return {
    body_solid: '几何体/实体',
    face: '面',
    loop: '边界环/线框',
    coedge: '有向边',
    edge: '边',
    vertex: '顶点'
  }[category];
}

function topologyKindLabel(kind: SelectionTarget['kind']) {
  return {
    assembly: '装配',
    part_instance: '零件实例',
    part: '零件',
    body: '几何体',
    solid: '实体',
    native_feature: '原生特征',
    recognized_feature: '识别特征',
    face: '面',
    loop: '边界环',
    coedge: '有向边',
    edge: '边',
    vertex: '顶点'
  }[kind];
}

watch(toolMode, applyToolMode);
watch([transparent, isolated, sectionEnabled, sectionOffset], applyVisualState);
onMounted(async () => {
  const savedWidth = Number(window.localStorage.getItem('feature-center:navigation-width'));
  if (Number.isFinite(savedWidth)) navigationWidth.value = Math.min(420, Math.max(288, savedWidth));
  initViewer();
  const requestedBuildId = typeof route.query.build_id === 'string' ? route.query.build_id : '';
  const recentBuildId = readRecentFeatureCenterBuildId(window.localStorage);
  const buildId = resolveFeatureCenterBuildId(requestedBuildId, recentBuildId);
  if (!buildId) return;
  if (!requestedBuildId) {
    await router.replace({ query: { ...route.query, build_id: buildId } });
  }
  await loadBuildBundle(buildId);
});
onBeforeUnmount(() => {
  clearStatusPoll();
  if (processTimer) window.clearInterval(processTimer);
  assetRequestController.abort();
  if (animationId) cancelAnimationFrame(animationId);
  resizeObserver?.disconnect();
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
    renderer.domElement.removeEventListener('pointerup', handlePointerUp);
  }
  controls?.removeEventListener('change', updateOrientationAxes);
  disposeModel(modelRoot);
  controls?.dispose();
  renderer?.dispose();
  renderer?.domElement.remove();
});
</script>

<template>
  <div class="feature-center-page">
    <header class="model-summary">
      <div class="summary-main">
        <strong>{{ contract?.summary.model_name || 'Feature Center' }}</strong>
        <span v-if="sourceFormat" class="format-badge">{{ sourceFormat === 'CATPRODUCT' ? 'CATProduct' : 'CATPart' }}</span>
        <span v-if="contract?.bom.part_count">{{ contract.bom.part_count }} 个零件</span>
        <span v-if="contract?.summary.solid_count">{{ contract.summary.solid_count }} 个 Solid</span>
        <span v-if="isCatiaNativeSource(sourceFormat)">{{ contract?.summary.native_feature_count ?? 0 }} 个原生特征</span>
        <span v-if="contract">{{ contract.summary.recognized_feature_count }} 个识别特征</span>
        <span v-if="contract" :class="mappingAvailable ? 'available' : 'muted'">
          Feature–Face {{ mappingAvailable ? '映射可用' : '映射不可用' }}
        </span>
        <span v-if="contract" class="stage-badge" :class="contract.status">
          {{ workerStageLabel(contract.current_stage) }}
        </span>
      </div>
      <div class="summary-actions">
        <button type="button" class="process-trigger" :disabled="!contract" @click="openProcessPanel">
          工艺生成
        </button>
        <button type="button" :disabled="!contract" @click="fitCamera">适应窗口</button>
        <button
          type="button"
          :disabled="!contract"
          :class="{ active: sectionEnabled }"
          @click="sectionEnabled = !sectionEnabled"
        >
          剖切
        </button>
        <button type="button" disabled title="测量工作流尚未接入当前 Viewer">测量</button>
        <button type="button" class="details-trigger" @click="toggleDetails">详情</button>
      </div>
    </header>

    <ElDrawer v-model="processPanelOpen" direction="rtl" size="430px" :with-header="false" class="process-drawer">
      <div class="process-drawer-content">
        <div class="process-drawer-heading">
          <div>
            <strong>相关工序</strong>
            <span>共 {{ prototypeProcessSteps.length }} 道工序</span>
          </div>
          <button type="button" aria-label="关闭工序面板" @click="closeProcessPanel">×</button>
        </div>

        <div v-if="processGenerating" class="process-generation-card">
          <div class="process-generation-copy">
            <span class="process-generation-icon"><SvgIcon icon="lucide:sparkles" /></span>
            <div>
              <strong>{{ processGenerating ? '相关工艺生成中' : '相关工艺已生成' }}</strong>
              <span>{{ processGenerating ? '正在根据零件与工序栏匹配工艺步骤' : '已从 AO 工序栏整理出可执行步骤' }}</span>
            </div>
          </div>
          <ElProgress :percentage="processProgress" :stroke-width="7" :show-text="false" />
          <span class="process-generation-percent">{{ processProgress }}%</span>
        </div>

        <ElCollapse v-if="!processGenerating" v-model="activeProcessSteps" class="process-list">
          <ElCollapseItem v-for="step in prototypeProcessSteps" :key="step.sequence" :name="step.sequence">
            <template #title>
              <div class="process-item-title">
                <span class="process-sequence">{{ step.sequence }}</span>
                <div>
                  <strong>{{ step.type }}</strong>
                </div>
              </div>
            </template>
            <div class="process-item-body">
              <dl>
                <template v-if="step.name">
                  <dt>名称</dt><dd>{{ step.name }}</dd>
                </template>
                <template v-if="step.specification">
                  <dt>图号/规格</dt><dd>{{ step.specification }}</dd>
                </template>
                <template v-if="step.version">
                  <dt>版次</dt><dd>{{ step.version }}</dd>
                </template>
                <template v-if="step.category">
                  <dt>分类</dt><dd>{{ step.category }}</dd>
                </template>
                <template v-if="step.quantity">
                  <dt>数量</dt><dd>{{ step.quantity }}</dd>
                </template>
                <template v-if="step.basis">
                  <dt>依据</dt><dd>{{ step.basis }}</dd>
                </template>
                <template v-if="step.remark">
                  <dt>{{ ['005', '010', '015', '020', '025', '030', '035'].includes(step.sequence) ? '工作内容说明' : '备注' }}</dt><dd>{{ step.remark }}</dd>
                </template>
              </dl>
            </div>
          </ElCollapseItem>
        </ElCollapse>
        <p class="process-drawer-hint"><SvgIcon icon="lucide:info" /> 点击工序卡片可展开依据、备注与规格信息</p>
      </div>
    </ElDrawer>

    <div v-if="showProcessingCard" class="processing-card">
      <div class="processing-copy">
        <strong>{{ processingStatusText }}</strong>
        <span>后端进度 {{ viewerProgress }}%</span>
      </div>
      <ElProgress :percentage="viewerProgress" :stroke-width="8" :show-text="false" class="processing-progress" />
      <button v-if="route.query.build_id" type="button" @click="loadBuildBundle(String(route.query.build_id))">
        重新检查
      </button>
    </div>

    <div v-if="showErrorCard" class="error-card">
      <strong>{{ isCatiaNativeSource(contract?.source_format) ? 'CATIA 处理未完成' : '模型处理未完成' }}</strong>
      <span>失败阶段：{{ workerStageLabel(contract?.current_stage) }}</span>
      <span v-if="contract?.error_code">错误码：{{ contract.error_code }}</span>
      <p>{{ errorText }}</p>
      <button v-if="route.query.build_id" type="button" @click="retryBuild">重试</button>
      <button v-if="route.query.build_id" type="button" @click="loadBuildBundle(String(route.query.build_id))">
        重新检查
      </button>
    </div>

    <main
      v-loading="loading"
      class="workspace"
      :class="{ 'bom-collapsed': !bomVisible, 'details-collapsed': !detailsOpen }"
      :style="workspaceStyle"
    >
      <aside class="navigation" :class="{ collapsed: !bomVisible }">
        <template v-if="bomVisible">
          <div class="panel-heading">
            <strong>装配与特征</strong>
            <button type="button" title="隐藏 BOM" @click="toggleBom">‹</button>
          </div>
          <div class="semantic-tabs">
            <button
              v-for="tab in sourceTabs"
              :key="tab"
              type="button"
              :class="{ active: activeTab === tab }"
              @click="activeTab = tab"
            >
              {{ tabLabel(tab) }}
            </button>
          </div>
          <div class="panel-scroll" :class="{ 'feature-tree-panel': activeTab === 'recognized' }">
            <ElTree
              v-if="activeTab === 'bom' && contract?.bom.nodes.length"
              :data="contract.bom.nodes"
              node-key="node_id"
              default-expand-all
              :props="{ label: 'name', children: 'children' }"
              highlight-current
              @node-click="selectBom"
            >
              <template #default="{ data }">
                <span class="tree-node">
                  <span>{{ data.name }}</span>
                  <small v-if="data.quantity > 1">×{{ data.quantity }}</small>
                </span>
              </template>
            </ElTree>
            <ElEmpty v-else-if="activeTab === 'bom'" description="当前文件没有装配 BOM" />

            <div v-show="activeTab === 'recognized'" class="feature-tab-content">
              <div class="feature-source-tabs">
                <button type="button" :class="{ active: featureSubTab === 'native' }" @click="featureSubTab = 'native'">
                  原生特征
                </button>
                <button
                  type="button"
                  :class="{ active: featureSubTab === 'recognized' }"
                  @click="featureSubTab = 'recognized'"
                >
                  识别特征
                </button>
              </div>
              <NativeFeatureTree
                v-show="featureSubTab === 'native'"
                :records="nativeFeatures"
                :source-file-name="contract?.summary.source_file_name || ''"
                :selected-id="selectedNativeTreeNodeId"
                :face-refs-by-feature-id="nativeFaceRefs"
                @select="selectNativeTreeNode"
                @properties="showNativeTreeNodeProperties"
              />
              <div v-show="featureSubTab === 'recognized'" class="recognized-feature-list">
                <button
                  v-for="feature in canonicalFeatures"
                  :key="feature.feature_center_id"
                  type="button"
                  class="list-card"
                  :class="{ active: selectedFeatureId === feature.feature_center_id }"
                  @click="selectFeature(feature.feature_center_id)"
                >
                  <strong>{{ feature.family }} / {{ feature.subtype }}</strong>
                  <span>{{ feature.feature_center_id }} · {{ feature.review_state }}</span>
                </button>
                <ElEmpty v-if="!canonicalFeatures.length" :description="recognizedEmptyDescription" />
              </div>
            </div>

            <template v-if="activeTab === 'geometry'">
              <div class="geometry-toolbar">
                <ElInput v-model="geometryKeyword" clearable placeholder="搜索编号或拓扑类型" class="geometry-search" />
                <ElDropdown trigger="click" @command="setGeometryCategory">
                  <button type="button" class="geometry-filter-button" title="过滤拓扑类型" aria-label="过滤拓扑类型">
                    <SvgIcon icon="lucide:list-filter" />
                  </button>
                  <template #dropdown>
                    <ElDropdownMenu>
                      <ElDropdownItem command="body_solid">几何体/实体</ElDropdownItem>
                      <ElDropdownItem command="face">面</ElDropdownItem>
                      <ElDropdownItem command="loop">边界环/线框</ElDropdownItem>
                      <ElDropdownItem command="coedge">有向边</ElDropdownItem>
                      <ElDropdownItem command="edge">边</ElDropdownItem>
                      <ElDropdownItem command="vertex">顶点</ElDropdownItem>
                    </ElDropdownMenu>
                  </template>
                </ElDropdown>
              </div>
              <div class="geometry-filter-label">当前过滤：{{ geometryCategoryLabel(geometryCategory) }}</div>
              <ElTree
                v-if="geometryTreeNodes.length"
                :data="geometryTreeNodes"
                node-key="id"
                :props="{ label: 'label', children: 'children' }"
                highlight-current
                @node-click="selectGeometryTreeNode"
              >
                <template #default="{ data }">
                  <span
                    class="geometry-tree-node"
                    :class="{ active: primarySelection?.id === data.id || selectedFaceId === data.id }"
                  >
                    <strong>{{ data.label }}</strong>
                    <small>{{ data.subtitle }}</small>
                  </span>
                </template>
              </ElTree>
              <button
                v-if="geometryCategory === 'face' && filteredFaces.length < topologyFaces.length"
                type="button"
                class="load-more"
                @click="geometryLimit += 160"
              >
                继续加载
              </button>
              <ElEmpty
                v-if="!geometryTreeNodes.length"
                :description="geometryEmptyDescription"
              />
            </template>
          </div>
          <div v-if="contract?.bom.assembly_mode === 'single_part'" class="panel-hint">单零件模式自动隐藏 BOM</div>
          <div class="navigation-resizer" title="拖动调整侧栏宽度" @pointerdown="startNavigationResize" />
        </template>
        <template v-else>
          <button
            type="button"
            class="rail-button"
            :class="{ 'active-icon': activeTab === 'bom' }"
            title="BOM 树"
            aria-label="BOM 树"
            @click="
              activeTab = 'bom';
              toggleBom();
            "
          >
            <SvgIcon icon="lucide:network" />
          </button>
          <button
            type="button"
            class="rail-button"
            :class="{ 'active-icon': activeTab === 'recognized' }"
            title="特征"
            aria-label="特征"
            @click="
              activeTab = 'recognized';
              toggleBom();
            "
          >
            <SvgIcon icon="lucide:tags" />
          </button>
          <button
            type="button"
            class="rail-button"
            :class="{ 'active-icon': activeTab === 'geometry' }"
            title="几何拓扑"
            aria-label="几何拓扑"
            @click="
              activeTab = 'geometry';
              toggleBom();
            "
          >
            <SvgIcon icon="lucide:waypoints" />
          </button>
          <button type="button" class="rail-button primary" title="显示 BOM" aria-label="显示 BOM" @click="toggleBom">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>
          </button>
        </template>
      </aside>

      <section class="viewer-shell">
        <div v-if="contract" class="breadcrumb">
          <span>{{ contract.summary.model_name }}</span>
          <span v-if="selectedBomNode">/ {{ selectedBomNode.name }}</span>
          <span v-else-if="selectedNativeFeature">
            / {{ selectedNativeFeature.display_name || selectedNativeFeature.feature_id }}
          </span>
          <span v-else-if="selectedFeature">/ {{ selectedFeature.subtype }}</span>
          <span v-else-if="selectedFace">/ {{ selectedFace.face_id }}</span>
        </div>
        <section ref="containerRef" class="viewer" />
        <ElEmpty
          v-if="!contract"
          class="viewer-empty"
          description="暂无 CATPart 解析结果，请从零件库打开已完成的 CATPart"
        />
        <CadViewerControls
          v-if="contract"
          :tool-mode="toolMode"
          :scene-mode="sceneMode"
          :transparent="transparent"
          :isolated="isolated"
          :section-enabled="sectionEnabled"
          :can-explode="canExplode"
          :can-isolate="canIsolate"
          @tool-change="toolMode = $event"
          @scene-mode-change="setSceneMode"
          @transparent-change="setTransparent"
          @isolated-change="setIsolated"
          @section-change="setSectionEnabled"
          @command="$event === 'fit' ? fitCamera() : openLayers()"
        />
        <OrientationGizmo v-if="contract" :axes="orientationAxes" @snap="snapCamera" />
        <ElSlider
          v-if="contract && sectionEnabled"
          v-model="sectionOffset"
          class="section-slider"
          :min="-200"
          :max="200"
        />
      </section>

      <aside class="details" :class="{ open: detailsOpen }">
        <div class="panel-heading">
          <strong>对象详情</strong>
          <button type="button" @click="toggleDetails">×</button>
        </div>
        <div class="details-scroll">
          <div v-if="contract" class="object-card">
            <span class="object-icon">◇</span>
            <div>
              <strong>{{ selectedTitle }}</strong>
              <small>{{ sourceFormat === 'CATPRODUCT' ? 'CATProduct' : sourceFormat === 'CATPART' ? 'CATPart' : 'STEP' }}</small>
            </div>
          </div>
          <section v-if="hasDetailGroup('part')" class="detail-section">
            <h4>零件属性</h4>
            <dl>
              <dt>零件号</dt>
              <dd>{{ contract?.summary.part_number || detailNode?.part_number || '—' }}</dd>
              <dt>零件名称</dt>
              <dd>{{ contract?.summary.part_name || detailNode?.name || '—' }}</dd>
              <dt>文件类型</dt>
              <dd>{{ sourceFormat === 'CATPRODUCT' ? 'CATProduct' : sourceFormat === 'CATPART' ? 'CATPart' : 'STEP' }}</dd>
              <dt>版本</dt>
              <dd>{{ detailNode?.version || contract?.summary.version || '—' }}</dd>
              <template v-if="detailNode?.material || contract?.summary.material">
                <dt>材料</dt>
                <dd>{{ detailNode?.material || contract?.summary.material }}</dd>
              </template>
            </dl>
          </section>
          <section v-if="hasDetailGroup('assembly_instance') && detailNode" class="detail-section">
            <h4>装配实例属性</h4>
            <dl>
              <dt>实例标识</dt>
              <dd>{{ detailNode.instance_name || '—' }}</dd>
              <dt>所属组件</dt>
              <dd>{{ detailParentNode?.name || '—' }}</dd>
              <dt>数量</dt>
              <dd>{{ detailNode.quantity }}</dd>
              <dt>装配层级</dt>
              <dd>{{ detailNode.level }}</dd>
              <dt>装配路径</dt>
              <dd>{{ detailNode.assembly_path || '—' }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('assembly') && detailNode" class="detail-section">
            <h4>装配属性</h4>
            <dl>
              <dt>装配号</dt>
              <dd>{{ detailNode.part_number || '—' }}</dd>
              <dt>装配名称</dt>
              <dd>{{ detailNode.name }}</dd>
              <dt>类型</dt>
              <dd>{{ detailNode.node_type === 'subassembly' ? '子装配' : '总装' }}</dd>
              <dt>子项数量</dt>
              <dd>{{ detailNode.children.length }}</dd>
              <dt>装配层级</dt>
              <dd>{{ detailNode.level }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('assembly_statistics') && detailNode" class="detail-section">
            <h4>装配统计</h4>
            <dl>
              <dt>直接子项</dt>
              <dd>{{ detailNode.children.length }}</dd>
              <dt>Solid</dt>
              <dd>{{ detailNode.solid_count || '—' }}</dd>
              <dt>体积</dt>
              <dd>{{ detailNode.volume == null ? '—' : `${detailNode.volume} mm³` }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('source')" class="detail-section">
            <h4>{{ isCatiaNativeSource(sourceFormat) ? '来源与特征' : '来源与识别结果' }}</h4>
            <dl>
              <dt>源文件</dt>
              <dd>{{ contract?.summary.source_file_name || '—' }}</dd>
              <template v-if="isCatiaNativeSource(sourceFormat)">
                <dt>原生特征</dt>
                <dd>{{ contract?.native_semantics?.available ? contract.summary.native_feature_count : '不可用' }}</dd>
              </template>
              <dt>识别特征</dt>
              <dd>{{ contract?.summary.recognized_feature_count ?? 0 }}</dd>
              <dt>Feature–Face 映射</dt>
              <dd :class="mappingAvailable ? 'available' : 'muted'">{{ mappingAvailable ? '可用' : '不可用' }}</dd>
            </dl>
          </section>
          <section v-if="primarySelection" class="detail-section">
            <h4>选择映射证据</h4>
            <dl>
              <dt>主对象</dt>
              <dd>{{ primarySelection.kind }} / {{ primarySelection.id }}</dd>
              <dt>映射状态</dt>
              <dd>{{ selectionContext.mappingStatus }}</dd>
              <dt>Authority</dt>
              <dd>{{ selectionContext.mappingAuthority || 'unavailable' }}</dd>
              <dt>Primitive</dt>
              <dd>{{ selectionContext.primitiveIds.length }}</dd>
              <dt>Render Face</dt>
              <dd>{{ selectionContext.renderFaceIds.join(', ') || '—' }}</dd>
              <dt>关联 Feature</dt>
              <dd>{{ selectionContext.recognizedFeatureIds.join(', ') || '—' }}</dd>
            </dl>
            <p v-if="selectionContext.edgeIds.length || selectionContext.vertexIds.length" class="muted">
              当前轻量化资产未提供独立边线/顶点渲染，已高亮可追溯的相邻 Face。
            </p>
            <p v-if="selectionContext.diagnostics.length" class="muted">
              {{ selectionContext.diagnostics.join('; ') }}
            </p>
          </section>
          <section v-if="hasDetailGroup('positioning') && detailNode" class="detail-section">
            <h4>装配定位</h4>
            <dl v-if="detailNode.instance_name || detailNode.constraint_status || detailNode.constraint_count != null">
              <dt>实例标识</dt>
              <dd>{{ detailNode.instance_name || '—' }}</dd>
              <dt>约束状态</dt>
              <dd>{{ detailNode.constraint_status || '未知' }}</dd>
              <dt v-if="detailNode.constraint_count != null">装配约束</dt>
              <dd v-if="detailNode.constraint_count != null">{{ detailNode.constraint_count }}</dd>
            </dl>
            <p v-else class="muted">当前实例未提供定位数据</p>
          </section>
          <section v-if="hasDetailGroup('feature') && selectedNativeFeature" class="detail-section">
            <h4>特征详情</h4>
            <dl>
              <dt>名称</dt>
              <dd>{{ selectedNativeTreeNode?.displayName || selectedNativeFeature.feature_id }}</dd>
              <dt>原生类型</dt>
              <dd>{{ selectedNativeTreeNode?.nativeType || '未提供' }}</dd>
              <dt>所属容器</dt>
              <dd>{{ selectedNativeTreeParent?.displayName || '未提供' }}</dd>
              <dt>建模顺序</dt>
              <dd>{{ selectedNativeFeature.traversal_index ?? '未提供' }}</dd>
              <dt>更新状态</dt>
              <dd>{{ selectedNativeFeature.update_status || '未提供' }}</dd>
              <dt>Decoder</dt>
              <dd>{{ selectedNativeFeature.decoder_status || selectedNativeFeature.decode_status || '未提供' }}</dd>
              <dt>Payload</dt>
              <dd>{{ selectedNativeFeature.payload_extraction_status || selectedNativeFeature.decode_level || '未提供' }}</dd>
              <dt>参数族</dt>
              <dd>{{ selectedNativeParameterFamily || '未提供' }}</dd>
            </dl>
            <h5>特征参数</h5>
            <dl v-if="selectedNativeParameters.length" class="parameter-list">
              <template v-for="entry in selectedNativeParameters" :key="entry[0]">
                <dt>{{ entry[0] }}</dt>
                <dd>{{ formatNativeAttribute(entry[1]) }}</dd>
              </template>
            </dl>
            <p v-else class="muted">暂无可用参数</p>
            <h5>关联几何</h5>
            <div v-if="selectedNativeFaces.length" class="face-links">
              <button v-for="faceId in selectedNativeFaces" :key="faceId" type="button" @click="openNativeFace(faceId)">
                {{ faceId }}
              </button>
            </div>
            <p v-else class="muted">未建立关联面</p>
          </section>
          <section v-if="hasDetailGroup('feature') && selectedFeature" class="detail-section">
            <h4>特征属性</h4>
            <dl>
              <dt>识别类型</dt>
              <dd>{{ selectedFeature.family }} / {{ selectedFeature.subtype }}</dd>
              <dt>复核状态</dt>
              <dd>{{ selectedFeature.review_state }}</dd>
              <dt>关联面</dt>
              <dd>{{ selectedFeature.geometry_refs.face_ids.join(', ') || '—' }}</dd>
              <dt>原生来源</dt>
              <dd>{{ selectedFeature.native_feature_ids.join(', ') || '—' }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('geometry') && selectedFace" class="detail-section">
            <h4>几何属性</h4>
            <dl>
              <dt>Face ID</dt>
              <dd>{{ selectedFace.face_id }}</dd>
              <dt>曲面类型</dt>
              <dd>{{ faceTypeLabel(selectedFace.surface_type) }}</dd>
              <dt>面积</dt>
              <dd>{{ selectedFace.area == null ? '—' : `${selectedFace.area} mm²` }}</dd>
              <dt>关联特征</dt>
              <dd>{{ faceFeatureIds.join(', ') || '无' }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('operations')" class="detail-section actions">
            <h4>快捷操作</h4>
            <button type="button" @click="applyVisualState">高亮</button>
            <button type="button" @click="isolated = !isolated">隔离</button>
            <button type="button" @click="transparent = !transparent">透明</button>
            <button type="button" disabled>设为测量对象</button>
            <button
              v-if="hasDetailGroup('source')"
              type="button"
              class="feature-link"
              :disabled="!detailLayout.featureLinkEnabled"
              @click="openFeatureLinks"
            >
              {{ detailLayout.featureLinkLabel }}
            </button>
          </section>
          <ElCollapse v-if="hasDetailGroup('topology')" class="advanced">
            <ElCollapseItem title="高级拓扑信息" name="topology">
              <pre>{{ selectedFace || selectedNativeFeature || selectedFeature || detailNode || '—' }}</pre>
            </ElCollapseItem>
          </ElCollapse>
        </div>
      </aside>
    </main>

    <ElDialog
      v-model="catiaPropertyDialogOpen"
      class="catia-property-dialog"
      :title="catiaPropertyTitle"
      width="640px"
      append-to-body
    >
      <div class="catia-current-selection">
        <span>当前选择：</span>
        <strong>{{ catiaPropertyNode?.sourceRef || catiaPropertyNode?.displayName || '—' }}</strong>
      </div>
      <ElTabs v-if="catiaPropertyTabs.length" v-model="catiaPropertyTab" type="card">
        <ElTabPane v-for="tab in catiaPropertyTabs" :key="tab.name" :label="tab.label" :name="tab.name">
          <section v-for="group in tab.groups" :key="group.title" class="catia-property-group">
            <h4>{{ group.title }}</h4>
            <dl v-if="group.rows.length">
              <template v-for="row in group.rows" :key="`${group.title}-${row.label}`">
                <dt>{{ row.label }}</dt>
                <dd :title="row.value">{{ row.value }}</dd>
              </template>
            </dl>
            <p v-else class="catia-property-empty">当前解析结果未提供</p>
          </section>
        </ElTabPane>
      </ElTabs>
      <ElEmpty v-else description="当前节点没有可显示的 CATIA 属性" />
      <template #footer>
        <ElButton @click="catiaPropertyDialogOpen = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.feature-center-page {
  display: flex;
  height: calc(100vh - 112px);
  min-height: 620px;
  flex-direction: column;
  gap: 10px;
  font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  color: var(--el-text-color-primary);
}
:global(.process-drawer) {
  font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Noto Sans CJK SC", sans-serif;
}
button {
  border: 1px solid var(--el-border-color-light);
  border-radius: 7px;
  background: white;
  color: inherit;
  cursor: pointer;
  padding: 7px 11px;
}
button:hover,
button.active {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
.model-summary {
  display: flex;
  min-height: 54px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  padding: 4px 14px;
}
.summary-main,
.summary-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.summary-main strong {
  font-size: 17px;
}
.summary-main span {
  font-size: 13px;
  white-space: nowrap;
}
.process-trigger {
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  font-weight: 600;
}
.format-badge,
.stage-badge {
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 6px;
  color: var(--el-color-primary);
  padding: 4px 10px;
}
.stage-badge.ready,
.available {
  color: var(--el-color-success);
}
.muted {
  color: var(--el-text-color-secondary);
}
.processing-card {
  display: grid;
  grid-template-columns: minmax(260px, max-content) minmax(180px, 1fr) auto;
  align-items: center;
  gap: 14px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  padding: 10px 14px;
}
.processing-copy {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
  color: var(--el-color-primary);
}
.processing-copy span {
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.processing-progress {
  min-width: 160px;
}
.error-card {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--el-color-danger-light-5);
  border-radius: 8px;
  background: var(--el-color-danger-light-9);
  padding: 10px 14px;
}
.error-card p {
  min-width: 0;
  flex: 1;
  margin: 0;
  overflow-wrap: anywhere;
}
:global(.process-drawer .el-drawer__body) {
  padding: 0;
}
.process-drawer-content {
  display: flex;
  height: 100%;
  flex-direction: column;
  background: var(--el-bg-color-page);
}
.process-drawer-heading {
  display: flex;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  padding: 0 16px;
}
.process-drawer-heading > div {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.process-drawer-heading strong {
  font-size: 16px;
}
.process-drawer-heading span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.process-drawer-heading button {
  border: 0;
  background: transparent;
  font-size: 22px;
  line-height: 1;
}
.process-generation-card {
  margin: 12px 14px 8px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 9px;
  background: var(--el-color-primary-light-9);
  padding: 12px;
}
.process-generation-copy {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.process-generation-icon {
  display: grid;
  width: 30px;
  height: 30px;
  border-radius: 7px;
  color: var(--el-color-primary);
  background: var(--el-color-primary);
  place-items: center;
}
.process-generation-icon :deep(svg),
.process-generation-icon :deep(svg *) {
  color: #fff !important;
  fill: currentColor !important;
  stroke: currentColor !important;
}
.process-generation-copy div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}
.process-generation-copy strong {
  font-size: 13px;
}
.process-generation-copy span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.process-generation-percent {
  display: block;
  margin-top: 4px;
  color: var(--el-color-primary);
  font-size: 12px;
  text-align: right;
}
.process-list {
  min-height: 0;
  flex: 1;
  overflow: auto;
  border: 0;
  padding: 10px 14px 0;
}
.process-list :deep(.el-collapse-item) {
  margin-bottom: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.process-list :deep(.el-collapse-item:last-child) {
  margin-bottom: 0;
}
.process-list :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 40px;
  align-items: center;
  border-bottom: 0;
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 7px 8px;
  line-height: 1.25;
}
.process-list :deep(.el-collapse-item__wrap) {
  border-top: 1px solid var(--el-border-color-lighter);
  border-bottom: 0;
  background: transparent;
}
.process-list :deep(.el-collapse-item__content) {
  padding: 10px;
}
.process-item-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
}
.process-sequence {
  flex: 0 0 auto;
  border-radius: 5px;
  color: #fff;
  background: var(--el-color-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 22px;
  padding: 0 6px;
}
.process-item-title > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}
.process-item-title strong {
  color: var(--el-text-color-primary);
  font-size: 13px;
}
.process-item-title small {
  display: -webkit-box;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.process-item-body {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
  background: var(--el-fill-color-lighter);
  padding: 10px;
}
.process-item-body dl {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 7px 10px;
  margin: 0;
  font-size: 12px;
}
.process-item-body dt {
  color: var(--el-text-color-secondary);
}
.process-item-body dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
.process-item-actions {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
}
.process-item-actions button {
  border: 0;
  color: var(--el-color-primary);
  background: transparent;
  font-size: 12px;
  padding: 0;
}
.process-drawer-hint {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  padding: 11px 14px;
}
.workspace {
  position: relative;
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: var(--navigation-width, 310px) minmax(0, 1fr) 330px;
  gap: 10px;
  transition: grid-template-columns 0.2s ease;
}
.workspace.bom-collapsed {
  grid-template-columns: 56px minmax(0, 1fr) 330px;
}
.workspace.details-collapsed {
  grid-template-columns: var(--navigation-width, 310px) minmax(0, 1fr) 0;
}
.workspace.bom-collapsed.details-collapsed {
  grid-template-columns: 56px minmax(0, 1fr) 0;
}
.navigation,
.viewer-shell,
.details {
  min-width: 0;
  min-height: 0;
  border-radius: 9px;
  background: var(--el-bg-color);
  overflow: hidden;
}
.navigation {
  position: relative;
  display: flex;
  flex-direction: column;
}
.navigation.collapsed {
  align-items: center;
  padding: 10px 5px;
  gap: 10px;
}
.panel-heading {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 0 14px;
}
.panel-heading button {
  border: 0;
  font-size: 20px;
  padding: 4px 8px;
}
.semantic-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.semantic-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  padding: 11px 4px;
}
.semantic-tabs button.active {
  border-bottom-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
.panel-scroll,
.details-scroll {
  min-height: 0;
  flex: 1;
  overflow: auto;
  padding: 10px;
}
.panel-scroll.feature-tree-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}
.feature-tab-content {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}
.feature-source-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 0 10px;
}
.feature-source-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  font-size: 12px;
  padding: 8px 4px;
}
.feature-source-tabs button.active {
  border-bottom-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
.recognized-feature-list {
  min-height: 0;
  flex: 1;
  overflow: auto;
  padding: 10px;
}
.panel-hint {
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  padding: 11px;
}
.navigation-resizer {
  position: absolute;
  z-index: 3;
  top: 0;
  right: -2px;
  bottom: 0;
  width: 5px;
  cursor: col-resize;
}
.navigation-resizer:hover {
  background: var(--el-color-primary-light-7);
}
.tree-node {
  display: flex;
  width: 100%;
  justify-content: space-between;
  gap: 8px;
}
.rail-button {
  display: grid;
  width: 42px;
  height: 42px;
  border: 0;
  place-items: center;
  padding: 0;
}
.rail-button svg {
  width: 22px;
  height: 22px;
  fill: none;
  stroke: currentcolor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.rail-button :deep(.svg-icon) {
  font-size: 21px;
}
.rail-button.active-icon {
  border-color: var(--el-color-primary-light-7);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.rail-button.primary {
  margin-top: 12px;
}
.list-card {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin-bottom: 7px;
  text-align: left;
}
.list-card span {
  max-width: 100%;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feature-group-title {
  margin: 5px 2px 9px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}
.geometry-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 36px;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.geometry-search {
  min-width: 0;
}
.geometry-filter-button {
  display: grid;
  width: 36px;
  height: 32px;
  border: 0;
  place-items: center;
  padding: 0;
}
.geometry-filter-button :deep(.svg-icon) {
  font-size: 17px;
}
.geometry-filter-label {
  margin: 0 2px 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.geometry-tree-node {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  line-height: 1.25;
}
.geometry-tree-node strong {
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
}
.geometry-tree-node small {
  max-width: 220px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.geometry-tree-node.active strong {
  color: var(--el-color-primary);
}
.load-more {
  width: 100%;
}
.viewer-shell {
  position: relative;
  background: #f7f8fb;
}
.viewer {
  position: absolute;
  inset: 0;
}
.viewer :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
  touch-action: none;
}
.viewer-empty {
  position: absolute;
  z-index: 1;
  inset: 0;
}
.breadcrumb {
  position: absolute;
  z-index: 2;
  top: 14px;
  left: 18px;
  display: flex;
  gap: 8px;
  border-radius: 7px;
  background: color-mix(in srgb, var(--el-bg-color) 82%, transparent);
  padding: 7px 11px;
  backdrop-filter: blur(6px);
  pointer-events: none;
}
.section-slider {
  position: absolute;
  z-index: 6;
  bottom: 142px;
  left: 50%;
  width: min(420px, 62%);
  transform: translateX(-50%);
}
.details {
  display: flex;
  flex-direction: column;
  transition: opacity 0.15s ease;
}
.details-collapsed .details {
  pointer-events: none;
  opacity: 0;
}
.object-card {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
}
.object-icon {
  color: var(--el-color-primary);
  font-size: 30px;
}
.object-card div {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.object-card small {
  color: var(--el-text-color-secondary);
}
.detail-section {
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 8px 0 12px;
}
.detail-section h4 {
  margin: 7px 0 10px;
}
.detail-section h5 {
  margin: 13px 0 8px;
  font-size: 13px;
}
.detail-section dl {
  display: grid;
  grid-template-columns: 95px 1fr;
  gap: 8px;
  margin: 0;
  font-size: 13px;
}
.detail-section dt {
  color: var(--el-text-color-secondary);
}
.detail-section dd {
  margin: 0;
  overflow-wrap: anywhere;
}
:global(.catia-property-dialog .el-dialog__body) {
  padding-top: 8px;
}
.catia-current-selection {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
}
.catia-current-selection span {
  color: var(--el-text-color-regular);
}
.catia-current-selection strong {
  min-width: 0;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-fill-color-lighter);
  font-weight: 500;
  overflow: hidden;
  padding: 5px 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.catia-property-group {
  border: 1px solid var(--el-border-color);
  margin: 8px 0 10px;
  padding: 12px 8px 8px;
  position: relative;
}
.catia-property-group h4 {
  position: absolute;
  top: -10px;
  left: 8px;
  background: var(--el-bg-color);
  font-size: 13px;
  font-weight: 500;
  margin: 0;
  padding: 0 5px;
}
.catia-property-group dl {
  display: grid;
  grid-template-columns: max-content minmax(118px, 1fr) max-content minmax(118px, 1fr) max-content minmax(118px, 1fr);
  gap: 6px 6px;
  align-items: center;
  margin: 0;
}
.catia-property-group dt {
  color: var(--el-text-color-primary);
  font-size: 12px;
  white-space: nowrap;
}
.catia-property-group dd {
  min-height: 26px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
  font-size: 12px;
  margin: 0;
  overflow: hidden;
  padding: 4px 6px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.catia-property-empty {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  margin: 2px 0 0;
}
.parameter-list dd {
  white-space: pre-wrap;
}
.face-links {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.face-links button {
  font-size: 12px;
  padding: 4px 7px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.actions h4 {
  width: 100%;
}
.actions .feature-link {
  width: 100%;
  margin-top: 2px;
  text-align: left;
}
.advanced pre {
  max-height: 230px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 11px;
}
.details-trigger {
  display: none;
}
@media (max-width: 1439px) {
  .workspace {
    grid-template-columns: min(var(--navigation-width, 300px), 300px) minmax(0, 1fr) 290px;
  }
  .workspace.bom-collapsed {
    grid-template-columns: 54px minmax(0, 1fr) 290px;
  }
  .summary-main {
    gap: 9px;
  }
}
@media (max-width: 1179px) {
  .workspace,
  .workspace.bom-collapsed,
  .workspace.details-collapsed,
  .workspace.bom-collapsed.details-collapsed {
    grid-template-columns: 250px minmax(0, 1fr);
  }
  .workspace.bom-collapsed,
  .workspace.bom-collapsed.details-collapsed {
    grid-template-columns: 54px minmax(0, 1fr);
  }
  .details {
    position: absolute;
    z-index: 12;
    top: 70px;
    right: 10px;
    bottom: 10px;
    width: min(340px, calc(100vw - 40px));
    box-shadow: var(--el-box-shadow-dark);
    transform: translateX(calc(100% + 24px));
    transition: transform 0.2s ease;
  }
  .details.open {
    transform: translateX(0);
  }
  .details-trigger {
    display: inline-block;
  }
}
@media (max-width: 899px) {
  .feature-center-page {
    height: calc(100vh - 96px);
    min-height: 520px;
  }
  .model-summary {
    align-items: flex-start;
    flex-direction: column;
    padding: 8px 10px;
  }
  .summary-main span:not(.format-badge):not(.stage-badge) {
    display: none;
  }
  .workspace,
  .workspace.bom-collapsed,
  .workspace.details-collapsed,
  .workspace.bom-collapsed.details-collapsed {
    grid-template-columns: 54px minmax(0, 1fr);
  }
  .navigation:not(.collapsed) {
    position: absolute;
    z-index: 11;
    top: 118px;
    bottom: 10px;
    left: 10px;
    width: min(300px, calc(100vw - 40px));
    box-shadow: var(--el-box-shadow-dark);
  }
  .viewer-tools {
    bottom: 20px;
    max-width: calc(100% - 24px);
  }
  .viewer-tools button {
    padding: 6px;
  }
}
</style>
