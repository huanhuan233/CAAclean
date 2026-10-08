<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  Box,
  Brush,
  Close,
  CollectionTag,
  Connection,
  Document,
  Menu,
  Operation,
  Refresh,
  ScaleToOriginal,
  Tickets,
  WarningFilled
} from '@element-plus/icons-vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { fetchComponentBuildMbdAnnotationDetail, fetchComponentBuildMbdNodeDetail, fetchComponentBuildNativeEvidence, fetchComponentBuildNativeNodeProperties, fetchComponentBuildRecognizedFeatureDetail, fetchComponentBuildViewer, fetchComponentBuildViewerAsset, fetchGeometrySnapshot, submitGeometryQuery, retryComponentBuild } from '@/service/api';
import type { MbdAnnotationRecord, MbdNodeRecord, MbdRelationRecord } from '@/service/api/cad';
import type { AssemblyEvidenceRecord, TubeClearanceRecord, TubePathRecord } from '@/service/api/cad';
import type { GeometryQueryResponse, GeometrySnapshotResponse, GeometryReferencePayload } from '@/service/api/cad';
import { useThemeStore } from '@/store/modules/theme';
import { sha256Buffer } from './modules/asset-integrity';
import { facesForFeature } from './modules/feature-center-bundle';
import type { CanonicalFeatureRecord, FeatureMeshMap } from './modules/feature-center-bundle';
import { buildDetailPanelLayout } from './modules/detail-panel';
import type { DetailGroup } from './modules/detail-panel';
import CadViewerControls from './modules/CadViewerControls.vue';
import type { SceneMode, ToolMode } from './modules/CadViewerControls.vue';
import NativeFeatureTree from './modules/NativeFeatureTree.vue';
import RecognizedFeatureExplorer from './modules/RecognizedFeatureExplorer.vue';
import MbdExplorer from './modules/MbdExplorer.vue';
import TopologyExplorer from './modules/TopologyExplorer.vue';
import AssemblyRelationExplorer from './modules/AssemblyRelationExplorer.vue';
import AssemblyRelationDetail from './modules/AssemblyRelationDetail.vue';
import TubeExplorer from './modules/TubeExplorer.vue';
import TubeDetail from './modules/TubeDetail.vue';
import { createTubePathOverlay } from './modules/tube-path-overlay';
import { tubeResultCanOverlay } from './modules/tube-result-context';
import { buildRecognizedFeatureItems } from './modules/recognized-feature-view-model';
import { mbdAnnotationTitle, mbdNodeTitle } from './modules/mbd-view-model';
import { adaptNativeTopologyRecord, adaptSelectionIndexRecord, buildTopologyItems, preferMappedTopologyFaces, topologyRecordKind } from './modules/topology-view-model';
import type { TopologyExplorerItem, TopologyInput, SourcedTopologyRecord } from './modules/topology-view-model';
import ObjectDetailPanel from './modules/ObjectDetailPanel.vue';
import OrientationGizmo from './modules/OrientationGizmo.vue';
import { createNativeDetailLoader, loadCaaNewNativeChildPage, loadCaaNewNativeRecords, loadCaaNewNodeProperties } from './modules/caa-new-loader';
import { mergeNativeDetail } from './modules/object-detail-panel';
import { createMeasurementSession } from './modules/measurement-session';
import type { MeasurementOperation } from './modules/measurement-session';
import { createMeasurementOverlay } from './modules/measurement-overlay';
import { createSketchOverlay } from './modules/sketch-overlay';
import type { NativeSketchPayload } from './modules/sketch-overlay';
import { nativeChildPages } from './modules/native-tree-loading';
import type { GizmoAxisPoint } from './modules/OrientationGizmo.vue';
import { registerCadPickables, resolveCadSelection } from './modules/cad-selection';
import { applySelectedMaterial, normalizeCssColorForThree, rememberMaterial, restoreMaterial } from './modules/viewer-highlight-material';
import { focusCameraOnObjects } from './modules/viewer-locate';
import { replaceSelectionSurfaceOverlay } from './modules/selection-surface-overlay';
import type { CadSelectionTarget } from './modules/cad-selection';
import { buildNativeFeatureTree, flattenFeatureTree } from './modules/native-feature-tree';
import type { FeatureTreeNode, NativeFeatureRecord } from './modules/native-feature-tree';
import {
  clearViewerSelection,
  emptySelectionContext,
  resolveViewerSelection,
  projectSelectionIds,
  selectionPrimaryId
} from './modules/viewer-selection';
import type {
  SelectionTarget,
  ViewerSelection,
  ViewerSelectionIndex
} from './modules/viewer-selection';
import {
  readRecentFeatureCenterBuildId,
  resolveFeatureCenterBuildId,
  saveRecentFeatureCenterBuildId
} from './modules/recent-result';
import {
  defaultBomVisible,
  isCatiaNativeSource,
  shouldBlockWorkspaceDuringLoad,
  shouldLoadNativeTreeDuringProcessing,
  tabsForSource,
  workerStageLabel
} from './modules/viewer-workspace';
import type { ViewerTab } from './modules/viewer-workspace';

defineOptions({ name: 'FeatureCenterViewer' });
const themeStore = useThemeStore();

// 大型 CATIA 模型的 Feature Center 契约和资产可能需要较长时间生成或传输。
const FEATURE_CENTER_REQUEST_TIMEOUT_MS = 30 * 60 * 1000;

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

const route = useRoute();
const router = useRouter();
const assetRequestController = new AbortController();
const containerRef = ref<HTMLDivElement | null>(null);
const contract = ref<Api.ComponentBuild.ViewerContract | null>(null);
const canonicalFeatures = ref<CanonicalFeatureRecord[]>([]);
const recognizedHasMore = ref(false);
const recognizedNextOffset = ref<number | null>(null);
const recognizedTotal = ref<number | null>(null);
const recognizedPageLoading = ref(false);
const recognizedListError = ref('');
const recognizedDetailLoading = ref(false);
const recognizedDetailError = ref('');
let recognizedDetailGeneration = 0;
const mbdAnnotationDetail = ref<MbdAnnotationRecord | null>(null);
const mbdNodeDetail = ref<MbdNodeRecord | null>(null);
const mbdRelations = ref<MbdRelationRecord[]>([]);
const mbdDetailLoading = ref(false);
const mbdDetailError = ref('');
let mbdDetailGeneration = 0;
const productPropertyDetail = ref<Api.ComponentBuild.NativeNodeProperties | null>(null);
const productPropertyLoading = ref(false);
const productPropertyError = ref('');
let productPropertyGeneration = 0;
const nativeFeatures = ref<NativeFeatureRecord[]>([]);
const loadingNativeChildren = ref(new Set<string>());
const failedNativeChildren = ref(new Set<string>());
let nativeTreeGeneration = 0;
const nativeParameterValues = ref<Record<string, string>>({});
const nativePropertyFactsBySubjectId = ref<Record<string, Record<string, unknown>>>({});
const topologyFaces = ref<TopologyFaceRecord[]>([]);
const topologyBodies = ref<SourcedTopologyRecord[]>([]);
const topologySolids = ref<SourcedTopologyRecord[]>([]);
const topologyLoops = ref<SourcedTopologyRecord[]>([]);
const topologyCoedges = ref<SourcedTopologyRecord[]>([]);
const topologyEdges = ref<SourcedTopologyRecord[]>([]);
const topologyVertices = ref<SourcedTopologyRecord[]>([]);
const topologyError = ref('');
const measurements = ref<MeasurementRecord[]>([]);
const featureMeshMap = ref<FeatureMeshMap | null>(null);
const faceMeshMap = ref<FaceMeshMap | null>(null);
const selectionIndex = ref<ViewerSelectionIndex | null>(null);
const viewerSelection = ref<ViewerSelection>(clearViewerSelection());
const geometrySnapshot = ref<GeometrySnapshotResponse | null>(null);
const geometryDetail = ref<GeometryQueryResponse | null>(null);
const geometryDetailLoading = ref(false);
const geometryDetailError = ref('');
let geometryDetailGeneration = 0;
let geometryDetailController: AbortController | null = null;
const measurementSession = createMeasurementSession(async (buildId, payload, signal) => {
  const response = await submitGeometryQuery(buildId, payload, { signal, silent: true });
  if (response.error || !response.data) throw response.error || new Error('数据库测量请求失败');
  return response.data;
});
const selectedFeatureId = ref('');
const selectedNativeFeatureId = ref('');
const nativeDetailLoader = createNativeDetailLoader();
const selectedNativeDetail = ref<Api.ComponentBuild.NativeNodeProperties | null>(null);
const nativeDetailLoading = ref(false);
const nativeDetailError = ref('');
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
const bomPanelMode = ref<'tree' | 'relations'>('tree');
const assemblySelection = ref<{ group: 'relations' | 'connections' | 'booleans'; record: AssemblyEvidenceRecord } | null>(null);
const tubeAvailable = ref(false);
const tubeSelection = ref<{ group: 'native' | 'step' | 'clearance'; record: TubePathRecord | TubeClearanceRecord;
  segment?: Record<string, unknown>; displayCurrent: boolean } | null>(null);
const featureSubTab = ref<'native' | 'recognized' | 'mbd' | 'tube'>('native');
const transparent = ref(false);
const isolated = ref(false);
const sectionEnabled = ref(false);
const sectionOffset = ref(0);
const selectedBomPrimitiveIds = ref<string[]>([]);
const navigationWidth = ref(360);
const toolMode = ref<ToolMode>('select');
const sceneMode = ref<SceneMode>('whole');
const selectionTarget = ref<CadSelectionTarget | null>(null);
const catiaPropertyDialogOpen = ref(false);
const catiaPropertyNode = ref<FeatureTreeNode | null>(null);
const catiaPropertyTab = ref('product');
const catiaPropertyApiTabs = ref<CatiaPropertyTab[] | null>(null);
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
let measurementOverlay: ReturnType<typeof createMeasurementOverlay> | null = null;
let relationOverlay: ReturnType<typeof createMeasurementOverlay> | null = null;
let tubePathOverlay: ReturnType<typeof createTubePathOverlay> | null = null;
let activeRelationPoints: { a: number[]; b: number[] } | null = null;
let sketchOverlay: ReturnType<typeof createSketchOverlay> | null = null;
let activeSketchPayload: NativeSketchPayload | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let modelRoot: THREE.Object3D | null = null;
let stepCurveRoot: THREE.Object3D | null = null;
let animationId = 0;
let resizeObserver: ResizeObserver | null = null;
let themeObserver: MutationObserver | null = null;
let statusPollTimer: number | null = null;
let processTimer: number | null = null;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const faceObjects = new Map<string, THREE.Mesh[]>();
const primitiveObjects = new Map<string, THREE.Mesh[]>();
const selectionSurfaceOverlay = new THREE.Group();
let pickableObjects: THREE.Object3D[] = [];
let pointerDownPosition: { x: number; y: number } | null = null;
const clippingPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
const workspaceStyle = computed(() => ({ '--navigation-width': `${navigationWidth.value}px` }));
// 大型装配只展开最外层节点，避免 ElTree 首次为整棵 BOM 创建大量 DOM。
const bomDefaultExpandedKeys = computed(() => (contract.value?.bom.nodes || []).map(node => node.node_id));
const canIsolate = computed(() => {
  if (selectedFaceId.value || selectedNativeFeatureId.value)
    return selectionContext.value.mappingStatus === 'exact' && selectionContext.value.primitiveIds.length > 0;
  if (selectedBomNode.value)
    return selectedBomPrimitiveIds.value.length > 0;
  return Boolean(featureMeshMap.value && facesForFeature(featureMeshMap.value, selectedFeatureId.value).length);
});
const canExplode = computed(() => contract.value?.bom.assembly_mode === 'assembly' && explodableGroupCount.value > 1);
const selectionContext = computed(() => viewerSelection.value.context || emptySelectionContext());
const primarySelection = computed(() => viewerSelection.value.primary);
const measurementSeedPoint = computed(() => {
  if (primarySelection.value?.kind !== 'face' || primarySelection.value.source !== 'canvas' ||
      selectionContext.value.mappingStatus !== 'exact' ||
      selectionTarget.value?.faceId !== primarySelection.value.id) return null;
  const hit = selectionTarget.value.raw as { point?: THREE.Vector3 } | undefined;
  const point = hit?.point;
  return point ? [point.x, point.y, point.z] : null;
});
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
const recognizedViewItems = computed(() => buildRecognizedFeatureItems(
  canonicalFeatures.value, contract.value?.task_id || '', featureMeshMap.value
));
const selectedRecognizedViewItem = computed(() =>
  recognizedViewItems.value.find(item => item.featureId === selectedFeatureId.value) ?? null
);
const selectedNativeFeature = computed(
  () => {
    const tree = nativeFeatures.value.find(item => item.feature_id === selectedNativeFeatureId.value) ?? null;
    if (!tree || selectedNativeDetail.value?.node_id !== tree.feature_id ||
        selectedNativeDetail.value.revision_id !== contract.value?.task_id) return tree;
    return mergeNativeDetail(tree, selectedNativeDetail.value);
  }
);
const selectedFace = computed(() => primarySelection.value?.kind === 'face'
  ? (primarySelection.value.raw as TopologyFaceRecord | null) : null);
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
  buildNativeFeatureTree(
    nativeFeatures.value,
    contract.value?.summary.source_file_name || '',
    nativeFaceRefs.value,
    nativeParameterValues.value
  )
);
const nativeTreeNodeIndex = computed(
  () => new Map(flattenFeatureTree(nativeTreeNodes.value).map(node => [node.id, node]))
);
const selectedNativeTreeNode = computed(() => nativeTreeNodeIndex.value.get(selectedNativeFeatureId.value) ?? null);
const selectedNativeTreeParent = computed(() => {
  const parentId = selectedNativeTreeNode.value?.parentId;
  return parentId ? (nativeTreeNodeIndex.value.get(parentId) ?? null) : null;
});
const selectedNativeParameterFamily = computed(() => {
  const payload = selectedNativeFeature.value?.native_feature_parameters as Record<string, unknown> | undefined;
  return String(payload?.family || selectedNativeFeature.value?.payload_type || '');
});
const selectedNativeFaces = computed(() => nativeFaceRefs.value[selectedNativeFeatureId.value] || []);
const topologyExplorerModel = computed(() => {
  const inputs: TopologyInput[] = [];
  const add = (category: TopologyInput['category'], records: SourcedTopologyRecord[]) => {
    for (const source of ['step_render', 'caa_native'] as const) {
      const subset = records.filter(record => record.topology_source === source);
      if (subset.length) inputs.push({ category, source, records: subset });
    }
  };
  add('body_solid', [...topologyBodies.value, ...topologySolids.value]);
  for (const source of ['step_render', 'caa_native'] as const) {
    const faces = topologyFaces.value.filter(face => (face.topology_source || 'step_render') === source);
    if (faces.length) inputs.push({ category: 'face', source, records: faces });
  }
  add('loop', topologyLoops.value);
  add('coedge', topologyCoedges.value);
  add('edge', topologyEdges.value);
  add('vertex', topologyVertices.value);
  return buildTopologyItems(inputs, contract.value?.task_id || '', new Set(Object.keys(faceMeshMap.value?.faces || {})));
});
const selectedTitle = computed(
  () => {
    const primary = primarySelection.value;
    if (primary?.kind === 'face') return primary.label || primary.id;
    if (primary?.kind === 'native_feature') return selectedNativeFeature.value?.display_name || primary.label || primary.id;
    if (primary?.kind === 'recognized_feature') return selectedRecognizedViewItem.value?.title || primary.label || primary.id;
    if (primary?.kind === 'mbd_annotation') return mbdAnnotationDetail.value ? mbdAnnotationTitle(mbdAnnotationDetail.value) : primary.label || primary.id;
    if (primary && ['mbd_set', 'mbd_view', 'mbd_capture'].includes(primary.kind))
      return mbdNodeDetail.value ? mbdNodeTitle(mbdNodeDetail.value) : primary.label || primary.id;
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
const catiaPropertyTabs = computed(() => catiaPropertyApiTabs.value ?? buildCatiaPropertyTabs(catiaPropertyNode.value));
const catiaPropertyName = computed(() => catiaPropertyNode.value?.displayName || 'CATIA 属性');
const catiaPropertyType = computed(
  () => catiaPropertyNode.value?.nativeType || catiaPropertyNode.value?.raw?.startup_type || catiaPropertyNode.value?.kind || ''
);

type CatiaPropertyRow = { key?: string; label: string; value: string; unit?: string };
type CatiaPropertyGroup = { title: string; rows: CatiaPropertyRow[] };
type CatiaPropertyTab = { name: string; label: string; groups: CatiaPropertyGroup[] };

const propertyIconMap = {
  实例名称: Box,
  类型: Connection,
  StartUp: Connection,
  内部名称: CollectionTag,
  零件编号: Document,
  更新状态: Refresh,
  体积: Box,
  质量: ScaleToOriginal,
  曲面: Tickets,
  密度: CollectionTag,
  颜色: Brush,
  线型: Operation,
  线宽: Menu
};

const catiaTabLabelMap: Record<string, string> = {
  product: '产品',
  graphic: '图形',
  graphics: '图形',
  mechanical: '机械',
  mass: '机械',
  drafting: '工程制图',
  drawing: '工程制图',
  attributes: '特征属性',
  attribute: '特征属性',
  feature_property: '特征属性',
  feature_properties: '特征属性'
};

const catiaGroupLabelMap: Record<string, string> = {
  occurrence: '部件',
  'product instance': '产品',
  product: '产品',
  identity: '特征属性',
  attributes: '特征属性',
  document: '文档',
  update: '更新状态',
  inertia: '特性',
  'inertia matrix': '惯性矩阵',
  'principal axes': '主轴',
  'principal moments': '主惯性',
  graphic: '图形属性',
  graphics: '图形属性',
  'graphic properties': '图形属性',
  surface: '填充',
  edge: '边线',
  line: '直线和曲线',
  point: '点',
  global: '全局属性',
  drafting: '工程制图'
};

const catiaFieldLabelMap: Record<string, string> = {
  instance_name: '实例名称',
  display_name: '名称',
  internal_name: '内部名称',
  startup_type: '类型',
  part_number: '零件编号',
  update_status: '更新状态',
  geometry_status: '几何状态',
  catia_property_mechanical_status: '机械状态',
  catia_property_density_kg_m3: '密度',
  catia_property_mass_kg: '质量',
  catia_property_volume_m3: '体积',
  catia_property_area_m2: '曲面',
  catia_property_center_x_mm: 'x',
  catia_property_center_y_mm: 'y',
  catia_property_center_z_mm: 'z',
  catia_property_ixx_kg_m2: 'Ixx',
  catia_property_ixy_kg_m2: 'Ixy',
  catia_property_ixz_kg_m2: 'Ixz',
  catia_property_iyx_kg_m2: 'Iyx',
  catia_property_iyy_kg_m2: 'Iyy',
  catia_property_iyz_kg_m2: 'Iyz',
  catia_property_izx_kg_m2: 'Izx',
  catia_property_izy_kg_m2: 'Izy',
  catia_property_izz_kg_m2: 'Izz',
  color: '颜色',
  rgb: '颜色',
  line_type: '线型',
  line_width: '线宽',
  transparency: '透明度',
  opacity: '透明度',
  layer: '图层',
  visible: '可视化',
  shown: '显示的',
  pickable: '可拾取',
  render_style: '渲染样式'
};

const hiddenCatiaPropertyKeys = new Set([
  'document_id',
  'object_id',
  'occurrence_id',
  'product_occurrence_id',
  'reference_id',
  'source_file_name',
  'source_file',
  'load_status',
  'native_document_open_status',
  'definition_status',
  'tree_path',
  'occurrence_path',
  'reference_path',
  'reference_link',
  'source_ref',
  'source_index',
  'transform_status',
  'source_api',
  'authority',
  'read_status',
  'normalization_status'
]);

function normalizeCatiaToken(value: string) {
  return value.trim().toLowerCase().replace(/[_-]+/g, ' ');
}

function normalizeCatiaTabId(tabId: string) {
  const normalized = normalizeCatiaToken(tabId).replace(/\s+/g, '_');
  if (['graphic', 'graphics'].includes(normalized)) return 'graphic';
  if (['mass', 'mechanical'].includes(normalized)) return 'mechanical';
  if (['drawing', 'drafting'].includes(normalized)) return 'drafting';
  if (['attribute', 'attributes', 'feature_property', 'feature_properties'].includes(normalized)) return 'feature_property';
  return normalized || 'feature_property';
}

function catiaDisplayLabel(value: string, fallback: string, map: Record<string, string>) {
  const normalized = normalizeCatiaToken(value || fallback);
  return map[normalized] || map[normalized.replace(/\s+/g, '_')] || fallback || value;
}

function catiaFieldLabel(key: string, displayName: string) {
  const normalizedKey = normalizeCatiaToken(key).replace(/\s+/g, '_');
  return catiaFieldLabelMap[normalizedKey] || catiaFieldLabelMap[normalizeCatiaToken(displayName)] || displayName || key;
}

function catiaGroupRows(tabName: string, groupTitle: string) {
  return catiaPropertyTabs.value.find(tab => tab.name === tabName)?.groups.find(group => group.title === groupTitle)?.rows || [];
}

function catiaRowValue(rows: CatiaPropertyRow[], label: string) {
  return rows.find(row => row.label === label)?.value;
}

function catiaFirstRow(rows: CatiaPropertyRow[], labels: string[]) {
  return rows.find(row => labels.includes(row.label) || (row.key && labels.includes(catiaFieldLabel(row.key, row.label))));
}

function catiaGraphicRows(tab: CatiaPropertyTab) {
  const rows = tab.groups.flatMap(group => group.rows);
  const pick = (labels: string[], fallback: string): CatiaPropertyRow => {
    const row = catiaFirstRow(rows, labels);
    return { key: row?.key, label: labels[0], value: row?.value || fallback, unit: row?.unit };
  };
  const summary: CatiaPropertyRow[] = [
    pick(['颜色'], '无颜色'),
    pick(['线型'], '无线型'),
    pick(['线宽'], '无宽度')
  ];
  const transparency = catiaFirstRow(rows, ['透明度']);
  if (transparency) summary.push({ ...transparency, label: '透明度' });
  return summary;
}

function iconForCatiaRow(row: CatiaPropertyRow) {
  return propertyIconMap[row.label as keyof typeof propertyIconMap] || Document;
}

function isWarningStatus(value: string) {
  return /not[_\s-]?up[_\s-]?to[_\s-]?date|failed|unavailable|error/i.test(value);
}

function shouldRenderCatiaStatus(row: CatiaPropertyRow) {
  return /状态|status/i.test(row.label) || isWarningStatus(row.value);
}

function catiaDisplayRows(group: CatiaPropertyGroup) {
  return group.rows.filter(row => row.value !== undefined && row.value !== null && row.value !== '');
}

function isInertiaGroup(group: CatiaPropertyGroup) {
  return group.title === '惯性矩阵';
}

function inertiaCell(rows: CatiaPropertyRow[], axisRow: string, axisColumn: string) {
  return catiaRowValue(rows, `I${axisRow.toLowerCase()}${axisColumn.toLowerCase()}`) || '—';
}

function groupUnit(group: CatiaPropertyGroup) {
  return group.rows.find(row => row.unit)?.unit;
}

function displayUnit(unit?: string) {
  if (!unit) return '';
  const unitMap: Record<string, string> = {
    m2: 'm²',
    m3: 'm³',
    kg_m3: 'kg/m³',
    kgxm2: 'kg·m²'
  };
  return unitMap[unit] || unit;
}

function apiPropertyValueText(value: unknown) {
  if (value === null || value === undefined || value === '') return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

const geometryStatusLabelMap: Record<string, string> = {
  exact: '有精确几何证据',
  mesh_available: '网格可用',
  topology_only: '仅有拓扑',
  partial: '部分可用',
  failed: '读取失败',
  not_available: '未取得几何',
  available: '几何可用'
};

// 中文：仅翻译数据库明确返回的状态；旧包缺字段时不推断或生成状态。
function apiFieldValueText(field: Api.ComponentBuild.NativePropertyField) {
  const value = apiPropertyValueText(field.display_value ?? field.raw_value);
  if (field.key !== 'geometry_status') return value;
  return geometryStatusLabelMap[value] || value;
}

// 隐藏内部属性页标记，业务字段仍按数据库返回值展示。
function isHiddenCatiaApiField(field: Api.ComponentBuild.NativePropertyField) {
  if ((field.key || '').trim().toLowerCase().startsWith('__catia_property_tab__')) return true;
  const key = normalizeCatiaToken(field.key || '').replace(/\s+/g, '_');
  if (hiddenCatiaPropertyKeys.has(key)) return true;
  const value = apiPropertyValueText(field.display_value ?? field.raw_value);
  return /^<local_path>\\/.test(value) || /^[a-z]:\\/i.test(value);
}

function mergeCatiaGroups(groups: CatiaPropertyGroup[]) {
  const merged = new Map<string, CatiaPropertyGroup>();
  for (const group of groups) {
    const existing = merged.get(group.title);
    if (existing) existing.rows.push(...group.rows);
    else merged.set(group.title, { title: group.title, rows: [...group.rows] });
  }
  return [...merged.values()];
}

// 数据库业务分组不受 CATIA 原生属性页声明限制，包括铺层、公式和工艺属性。
function apiTabsToCatiaTabs(tabs: Api.ComponentBuild.NativePropertyTab[]) {
  const mappedTabs = tabs
    .map<CatiaPropertyTab | null>(tab => {
      const name = normalizeCatiaTabId(tab.tab_id || tab.tab_label);
      const groups = mergeCatiaGroups(
        tab.groups.map(group => {
          const rawGroupLabel = group.group_label || group.group_id;
          const title = catiaDisplayLabel(rawGroupLabel, rawGroupLabel, catiaGroupLabelMap);
          const rows = group.fields
            .filter(field => !isHiddenCatiaApiField(field))
            .map(field => {
              const value = apiFieldValueText(field);
              if (!value) return null;
              return {
                key: field.key,
                label: catiaFieldLabel(field.key, field.display_name),
                value,
                unit: field.display_unit || field.raw_unit || undefined
              };
            })
            .filter(Boolean) as CatiaPropertyRow[];
          return { title, rows };
        })
      );
      return {
        name,
        label: catiaDisplayLabel(name, tab.tab_label || tab.tab_id || name, catiaTabLabelMap),
        groups
      };
    })
    .filter(Boolean) as CatiaPropertyTab[];

  const tabsByName = new Map<string, CatiaPropertyTab>();
  for (const tab of mappedTabs) {
    const existing = tabsByName.get(tab.name);
    if (existing) existing.groups = mergeCatiaGroups([...existing.groups, ...tab.groups]);
    else tabsByName.set(tab.name, tab);
  }
  return [...tabsByName.values()];
}

function isAxisRow(row: CatiaPropertyRow) {
  return ['x', 'y', 'z'].includes(row.label.toLowerCase());
}

// 用途：详情区只格式化真实解析值；对象和数组保留 JSON 结构，不补默认参数。
function formatNativeAttribute(value: unknown) {
  if (value == null) return '未提供';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function nativeAttributesOf(node: FeatureTreeNode | null) {
  if (!node) return {};
  const objectId = String(node.raw?.source_object_id || '');
  const factAttrs = objectId ? nativePropertyFactsBySubjectId.value[objectId] || {} : {};
  return {
    ...((node.raw?.attributes || {}) as Record<string, unknown>),
    ...factAttrs
  };
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
  return { label, value: text, unit };
}

function compactRows(rows: Array<{ label: string; value: string } | null>) {
  return rows.filter(Boolean) as Array<{ label: string; value: string }>;
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
    navigationWidth.value = Math.min(460, Math.max(320, startWidth + moveEvent.clientX - startX));
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
  const result = await fetchComponentBuildViewerAsset(path, {
    signal: assetRequestController.signal,
    silent: true,
    timeout: FEATURE_CENTER_REQUEST_TIMEOUT_MS
  });
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

let progressiveNativeTreeBuildId = '';

async function loadBuildBundle(buildId: string) {
  clearStatusPoll();
  assemblySelection.value = null;
  tubeSelection.value = null;
  if (contract.value?.part_id !== buildId) tubeAvailable.value = false;
  tubePathOverlay?.clear();
  geometrySnapshot.value = null;
  measurementSession.clear();
  measurementOverlay?.clear();
  loading.value = shouldBlockWorkspaceDuringLoad(Boolean(contract.value));
  errorText.value = '';
  explicitError.value = false;
  try {
    const result = await fetchComponentBuildViewer(buildId, {
      signal: assetRequestController.signal,
      silent: true,
      timeout: FEATURE_CENTER_REQUEST_TIMEOUT_MS
    });
    if (result.error || !result.data) throw result.error || new Error('Viewer 契约不可用');
    contract.value = result.data;
    await nextTick();
    if (!renderer) initViewer();
    bomVisible.value = defaultBomVisible(result.data.bom);
    activeTab.value = 'bom';
    if (result.data.status !== 'ready') {
      if (
        shouldLoadNativeTreeDuringProcessing(result.data) &&
        progressiveNativeTreeBuildId !== buildId
      ) {
        await loadOptionalSemanticAssets(result.data);
        if (nativeFeatures.value.length > 0) progressiveNativeTreeBuildId = buildId;
        clearSelection();
      }
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
    if (!viewerAsset) {
      canonicalFeatures.value = [];
      recognizedTotal.value = null;
      recognizedListError.value = '';
      measurements.value = [];
      featureMeshMap.value = null;
      faceMeshMap.value = null;
      await loadOptionalSemanticAssets(result.data);
      clearSelection();
      saveRecentFeatureCenterBuildId(window.localStorage, buildId);
      return;
    }
    const skipStepViewer = false;
    // 当前按完整 CATProduct 结果加载 STEP/GLB，确保装配模型和原生特征同时可见。
    const manifestBuffer = await fetchAsset(viewerAsset.scene_manifest_url);
    const decode = (buffer: ArrayBuffer) => new TextDecoder('utf-8').decode(buffer);
    const manifest = JSON.parse(decode(manifestBuffer)) as BundleManifest;
    if (manifest.schema_version !== 'cad_feature_center_v1') throw new Error('Feature Center Schema 不兼容');
    const requiredBuffers: Array<readonly [string, ArrayBuffer]> = [];
    let nextFeatureMap: FeatureMeshMap | null = null;
    let nextFaceMap: FaceMeshMap | null = null;
    let modelBuffer: ArrayBuffer | null = null;
    if (!skipStepViewer) {
      const nextFaceMapBuffer = await fetchAsset(viewerAsset.face_mesh_map_url);
      const featureMapBuffer = await fetchAsset(viewerAsset.feature_mesh_map_url);
      const modelAsset = await fetchAsset(viewerAsset.glb_url);
      modelBuffer = modelAsset;
      requiredBuffers.push(
        ['lightweight/face_mesh_map.json', nextFaceMapBuffer],
        ['lightweight/feature_mesh_map.json', featureMapBuffer],
        ['lightweight/model.glb', modelAsset]
      );
      nextFeatureMap = JSON.parse(decode(featureMapBuffer)) as FeatureMeshMap;
      nextFaceMap = JSON.parse(decode(nextFaceMapBuffer)) as FaceMeshMap;
    }
    for (const [relativePath, buffer] of requiredBuffers) {
      const expected = manifest.output_files[relativePath]?.sha256;
      if (!expected || (await sha256Buffer(buffer)) !== expected)
        throw new Error(`Bundle 文件哈希不匹配：${relativePath}`);
    }
    if (
      !skipStepViewer &&
      (!nextFeatureMap || !nextFaceMap ||
        nextFeatureMap.shape_hash !== manifest.brep.shape_hash ||
        nextFaceMap.shape_hash !== manifest.brep.shape_hash)
    ) {
      throw new Error('Mesh 映射与 B-Rep Shape Hash 不一致');
    }

    const featurePage = await fetchComponentBuildNativeEvidence<Record<string, unknown>>(
      buildId, 'canonical_features', 0, 100, { signal: assetRequestController.signal, silent: true }
    );
    if (featurePage.error || !featurePage.data) {
      canonicalFeatures.value = [];
      recognizedTotal.value = null;
      recognizedHasMore.value = false;
      recognizedNextOffset.value = 0;
      recognizedListError.value = featurePage.error instanceof Error ? featurePage.error.message : '识别特征列表读取失败';
    } else {
      canonicalFeatures.value = featurePage.data.records as unknown as CanonicalFeatureRecord[];
      recognizedTotal.value = featurePage.data.total;
      recognizedHasMore.value = featurePage.data.has_more;
      recognizedNextOffset.value = featurePage.data.next_offset;
      recognizedListError.value = '';
    }
    measurements.value = [];
    featureMeshMap.value = nextFeatureMap;
    faceMeshMap.value = nextFaceMap;
    if (modelBuffer) await loadGlb(modelBuffer);
    await loadStepCurves(viewerAsset.curves_url, manifest);
    await loadOptionalSemanticAssets(result.data);
    clearSelection();
    void loadGeometrySnapshot(buildId);
    saveRecentFeatureCenterBuildId(window.localStorage, buildId);
  } catch (error) {
    explicitError.value = true;
    errorText.value = error instanceof Error ? error.message : 'Web Viewer 加载失败';
    topologyError.value = errorText.value;
  } finally {
    loading.value = false;
  }
}

async function loadGeometrySnapshot(buildId: string) {
  const response = await fetchGeometrySnapshot(buildId, { signal: assetRequestController.signal, silent: true });
  if (contract.value?.part_id !== buildId) return;
  geometrySnapshot.value = response.error ? null : response.data || null;
  if (geometrySnapshot.value) void loadGeometryDetail();
}

function currentGeometryReference(): GeometryReferencePayload | null {
  const selected = primarySelection.value;
  const snapshot = geometrySnapshot.value;
  if (!selected || !snapshot) return null;
  if (!['face', 'edge', 'vertex', 'solid'].includes(selected.kind)) return null;
  if (selected.source === 'canvas' && selectionContext.value.mappingStatus !== 'exact') return null;
  if (sceneMode.value === 'explode') return null;
  return { revision_id: snapshot.revision_id, geometry_snapshot_id: snapshot.geometry_snapshot_id,
    entity_id: selected.id };
}

async function loadGeometryDetail() {
  const generation = ++geometryDetailGeneration;
  geometryDetailController?.abort();
  geometryDetailController = new AbortController();
  geometryDetail.value = null;
  geometryDetailError.value = '';
  const reference = currentGeometryReference();
  const buildId = contract.value?.part_id;
  if (!reference || !buildId) return;
  geometryDetailLoading.value = true;
  try {
    const response = await submitGeometryQuery(buildId, {
      operation: 'detail', references: [reference], parameters: {}, source_policy: 'auxiliary_brep'
    }, { signal: geometryDetailController.signal, silent: true });
    if (generation !== geometryDetailGeneration) return;
    if (response.error || !response.data) throw response.error || new Error('几何详情读取失败');
    geometryDetail.value = response.data;
    if (response.data.status !== 'success') geometryDetailError.value = response.data.diagnostic || response.data.status;
  } catch (reason) {
    if (generation === geometryDetailGeneration)
      geometryDetailError.value = reason instanceof Error ? reason.message : '几何详情读取失败';
  } finally {
    if (generation === geometryDetailGeneration) geometryDetailLoading.value = false;
  }
}

function startMeasurement(operation: Exclude<MeasurementOperation, 'idle'>) {
  measurementSession.start(operation);
  const reference = currentGeometryReference();
  if (reference) measurementSession.capture(reference, measurementSeedPoint.value);
  detailsOpen.value = true;
}

async function calculateMeasurement(parameters: Record<string, unknown>) {
  const buildId = contract.value?.part_id;
  if (!buildId) return;
  measurementSession.parameters.value = parameters;
  await measurementSession.calculate(buildId);
  const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
  measurementOverlay?.show(measurementSession.result.value, color);
}

function clearMeasurement() {
  measurementSession.clear();
  measurementOverlay?.clear();
}

function showNativeSketch() {
  const feature = selectedNativeDetail.value?.native_feature as Record<string, unknown> | undefined;
  const payload = feature?.native_sketch as NativeSketchPayload | undefined;
  if (!payload?.elements?.length) return;
  activeSketchPayload = payload;
  const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
  sketchOverlay?.show(payload, color);
}

function hideNativeSketch() {
  activeSketchPayload = null;
  sketchOverlay?.clear();
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

// 用途：分阶段读取原生 CAA Feature 与 B-Rep Face，避免大型装配同时保留多个完整 ArrayBuffer。
async function loadOptionalSemanticAssets(viewerContract: Api.ComponentBuild.ViewerContract) {
  nativeTreeGeneration += 1;
  loadingNativeChildren.value.clear();
  failedNativeChildren.value.clear();
  nativeFeatures.value = [];
  nativeParameterValues.value = {};
  topologyFaces.value = [];
  topologyBodies.value = [];
  topologySolids.value = [];
  topologyLoops.value = [];
  topologyCoedges.value = [];
  topologyEdges.value = [];
  topologyVertices.value = [];
  topologyError.value = '';
  nativePropertyFactsBySubjectId.value = {};
  nativeDetailLoader.clear();
  selectedNativeDetail.value = null;
  nativeDetailError.value = '';
  nativeDetailLoading.value = false;
  selectionIndex.value = null;
  let loadedNativeTreeFromApi = false;
  if (viewerContract.native_capture?.has_tree && viewerContract.part_id) {
    nativeFeatures.value = await loadCaaNewNativeRecords(viewerContract.part_id, {
      signal: assetRequestController.signal,
      silent: true
    });
    loadedNativeTreeFromApi = true;
  }
  // 原生树和拓扑只读取已经完整入库的记录；旧包需重新导入，绝不从 JSONL 兜底。
  if (viewerContract.status === 'ready' && isCatiaNativeSource(viewerContract.source_format) && !loadedNativeTreeFromApi)
    throw new Error('原生树尚未完整入 PostgreSQL，请重新导入该模型');
  if (viewerContract.status === 'ready' && viewerContract.feature_center.bundle_available) {
    const buildId = typeof route.query.build_id === 'string' ? route.query.build_id : '';
    if (!buildId) throw new Error('缺少构建任务编号');
    const indexRows = hasStoredEvidence(viewerContract, 'selection_index', true)
      ? await loadNativeEvidencePages(buildId, 'selection_index') : [];
    if (indexRows.length > 0) {
      selectionIndex.value = indexRows[0] as unknown as ViewerSelectionIndex;
      hydrateTopologyFromSelectionIndex(selectionIndex.value);
    }
  }
  if (viewerContract.status === 'ready' && viewerContract.source_format === 'CATPART') {
    const buildId = typeof route.query.build_id === 'string' ? route.query.build_id : '';
    if (!buildId) throw new Error('缺少构建任务编号');
    if (viewerContract.feature_center.bundle_available) {
      const faces = hasStoredEvidence(viewerContract, 'topology_faces', true)
        ? await loadNativeEvidencePages(buildId, 'topology_faces') : [];
      topologyFaces.value = preferMappedTopologyFaces(topologyFaces.value, faces as unknown as TopologyFaceRecord[]);
    }
    const cells = hasStoredEvidence(viewerContract, 'topology_cells')
      ? await loadNativeEvidencePages(buildId, 'topology_cells') : [];
    hydrateNativeCells(cells.map(raw => adaptNativeTopologyRecord(raw,
      String(raw.cell_kind || '').toLowerCase() === 'face' ? 'face' :
      String(raw.cell_kind || '').toLowerCase() === 'edge' ? 'edge' :
      String(raw.cell_kind || '').toLowerCase() === 'vertex' ? 'vertex' : 'solid')));
    topologyBodies.value = (hasStoredEvidence(viewerContract, 'topology_bodies')
      ? await loadNativeEvidencePages(buildId, 'topology_bodies') : []).map(raw => adaptNativeTopologyRecord(raw, 'body'));
    topologyLoops.value = (hasStoredEvidence(viewerContract, 'topology_wires')
      ? await loadNativeEvidencePages(buildId, 'topology_wires') : []).map(raw => adaptNativeTopologyRecord(raw, 'loop'));
    topologyCoedges.value = (hasStoredEvidence(viewerContract, 'topology_coedges')
      ? await loadNativeEvidencePages(buildId, 'topology_coedges') : []).map(raw => adaptNativeTopologyRecord(raw, 'coedge'));
    if (hasStoredEvidence(viewerContract, 'feature_topology_links'))
      mergeNativeFeatureTopologyLinks(await loadNativeEvidencePages(buildId, 'feature_topology_links'));
  }
}

function hasStoredEvidence(contract: Api.ComponentBuild.ViewerContract, kind: string, feature = false) {
  const counts = feature ? contract.native_capture?.feature_evidence_counts : contract.native_capture?.evidence_counts;
  return Object.hasOwn(counts || {}, kind);
}

// 用途：逐页取得 PostgreSQL 语义事实；任一页失败时不展示局部 JSONL 数据。
async function loadNativeEvidencePages(buildId: string, kind: string): Promise<Array<Record<string, unknown>>> {
  const records: Array<Record<string, unknown>> = [];
  let offset = 0;
  while (true) {
    const result = await fetchComponentBuildNativeEvidence<Record<string, unknown>>(
      buildId, kind, offset, 1000, { signal: assetRequestController.signal, silent: true }
    );
    if (result.error || !result.data) throw result.error || new Error(`数据库语义 ${kind} 不可用`);
    records.push(...result.data.records);
    if (!result.data.has_more) return records;
    if (result.data.next_offset == null || result.data.next_offset <= offset)
      throw new Error(`数据库语义 ${kind} 分页异常`);
    offset = result.data.next_offset;
  }
}

function hydrateTopologyFromSelectionIndex(index: ViewerSelectionIndex | null) {
  topologyBodies.value = Object.values(index?.topology?.bodies || {}).map(adaptSelectionIndexRecord);
  topologySolids.value = Object.values(index?.topology?.solids || {}).map(adaptSelectionIndexRecord);
  if (!topologyFaces.value.length) topologyFaces.value = Object.values(index?.topology?.faces || {}).map(record => ({
    ...(record.raw || {}), face_id: record.id, topology_source: 'step_render'
  } as TopologyFaceRecord));
  topologyLoops.value = [
    ...Object.values(index?.topology?.loops || {}),
    ...Object.values(index?.topology?.wires || {})
  ].map(adaptSelectionIndexRecord);
  topologyCoedges.value = Object.values(index?.topology?.coedges || {}).map(adaptSelectionIndexRecord);
  topologyEdges.value = Object.values(index?.topology?.edges || {}).map(adaptSelectionIndexRecord);
  topologyVertices.value = Object.values(index?.topology?.vertices || {}).map(adaptSelectionIndexRecord);
}

function hydrateNativeCells(records: SourcedTopologyRecord[]) {
  const cells = records;
  topologyFaces.value = topologyFaces.value.length
    ? topologyFaces.value
    : cells
      .filter(record => topologyRecordKind(record) === 'face')
      .map(record => ({
        ...(record.raw || {}),
        face_id: record.id,
        topology_source: 'caa_native',
        surface_type: String((record.raw || {}).surface_type || (record.raw || {}).kernel_surface_type || '')
      }));
  topologySolids.value = [...topologySolids.value, ...cells.filter(record => topologyRecordKind(record) === 'solid')];
  topologyEdges.value = [...topologyEdges.value, ...cells.filter(record => topologyRecordKind(record) === 'edge')];
  topologyVertices.value = [...topologyVertices.value, ...cells.filter(record => topologyRecordKind(record) === 'vertex')];
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
  replaceSelectionSurfaceOverlay(selectionSurfaceOverlay, [], '', false);
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
  if (target.kind !== 'assembly_relation') assemblySelection.value = null;
  if (!['tube_path', 'tube_segment', 'tube_clearance'].includes(target.kind)) tubeSelection.value = null;
  tubePathOverlay?.clear();
  relationOverlay?.clear();
  activeRelationPoints = null;
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
  const reference = currentGeometryReference();
  if (reference && measurementSession.operation.value !== 'idle') {
    measurementSession.capture(reference, measurementSeedPoint.value);
    measurementOverlay?.clear();
  }
  void loadGeometryDetail();
  if (target.kind === 'native_feature') void loadSelectedNativeDetail(target.id);
  else {
    nativeDetailLoader.cancel();
    selectedNativeDetail.value = null;
    nativeDetailError.value = '';
    nativeDetailLoading.value = false;
  }
  if (target.kind === 'recognized_feature') void loadSelectedRecognizedDetail(target.id);
  else {
    recognizedDetailGeneration += 1;
    recognizedDetailLoading.value = false;
    recognizedDetailError.value = '';
  }
  if (target.kind === 'mbd_annotation' || ['mbd_set', 'mbd_view', 'mbd_capture'].includes(target.kind))
    void loadSelectedMbdDetail(target);
  else {
    mbdDetailGeneration += 1;
    mbdAnnotationDetail.value = null;
    mbdNodeDetail.value = null;
    mbdRelations.value = [];
    mbdDetailLoading.value = false;
    mbdDetailError.value = '';
  }
  if (['assembly', 'part_instance', 'part'].includes(target.kind)) {
    const node = findBomNode(contract.value?.bom.nodes || [], target.id);
    if (node?.native_node_id) void loadSelectedProductProperties(node.native_node_id, target.id);
    else {
      productPropertyGeneration += 1;
      productPropertyDetail.value = null;
      productPropertyLoading.value = false;
      productPropertyError.value = isCatiaNativeSource(sourceFormat.value || '') ? '当前 BOM 对象缺少原生节点身份' : '';
    }
  } else {
    productPropertyGeneration += 1;
    productPropertyDetail.value = null;
    productPropertyLoading.value = false;
    productPropertyError.value = '';
  }
  applyVisualState();
}

function selectAssemblyRelation(group: 'relations' | 'connections' | 'booleans', record: AssemblyEvidenceRecord) {
  const id = String(record.relation_id || record.connection_id || record.result_version || '');
  if (!id) return;
  assemblySelection.value = { group, record };
  selectTarget({ kind: 'assembly_relation', id, label: '装配关系', raw: record }, 'assembly');
  detailsOpen.value = true;
}

function selectTube(group: 'native' | 'step' | 'clearance', record: TubePathRecord | TubeClearanceRecord,
                    segment?: Record<string, unknown>, run?: Record<string, unknown> | null) {
  const id = group === 'clearance' ? (record as TubeClearanceRecord).clearance_id : (record as TubePathRecord).path_id;
  if (!id) return;
  const displayCurrent = tubeResultCanOverlay(record, run || null, contract.value?.task_id,
    geometrySnapshot.value?.geometry_snapshot_id);
  tubeSelection.value = { group, record, segment, displayCurrent };
  selectTarget({ kind: group === 'clearance' ? 'tube_clearance' : segment ? 'tube_segment' : 'tube_path',
    id: segment ? `${id}:${segment.source_id || segment.order}` : id,
    label: group === 'clearance' ? '导管安装间隙' : segment ? '中心线段' : '导管路径',
    raw: { ...record, display_current: displayCurrent } }, 'tube');
  detailsOpen.value = true;
  if (!displayCurrent) return;
  if (group === 'clearance') {
    const witness = (record as TubeClearanceRecord).witnesses?.[0];
    if (witness?.tube?.length === 3 && witness.target?.length === 3) {
      activeRelationPoints = { a: witness.tube, b: witness.target };
      redrawRelationOverlay();
    }
    return;
  }
  const path = (record as TubePathRecord).path || {};
  const rawSegments = segment ? [segment] : Array.isArray(path.segments) ? path.segments as Array<Record<string, unknown>>
    : path.kind === 'straight' ? [{ kind: 'line', start_mm: path.start_mm, end_mm: path.end_mm }] : [];
  if (group === 'native' && sourceFormat.value !== 'CATPART') return;
  const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
  tubePathOverlay?.show(rawSegments, color);
}

function onTubeRecomputed() {
  tubeSelection.value = null;
  tubePathOverlay?.clear();
  relationOverlay?.clear();
  activeRelationPoints = null;
  if (primarySelection.value?.source === 'tube') {
    viewerSelection.value = clearViewerSelection();
    selectionTarget.value = null;
    applyVisualState();
  }
}

async function loadSelectedProductProperties(nativeNodeId: string, selectionId: string) {
  const buildId = contract.value?.part_id;
  const revisionId = contract.value?.task_id;
  if (!buildId || !revisionId) return;
  const generation = ++productPropertyGeneration;
  productPropertyDetail.value = null;
  productPropertyLoading.value = true;
  productPropertyError.value = '';
  try {
    const response = await fetchComponentBuildNativeNodeProperties(buildId, nativeNodeId, { silent: true });
    if (response.error || !response.data) throw response.error || new Error('产品属性不可用');
    if (generation !== productPropertyGeneration || contract.value?.task_id !== revisionId ||
        primarySelection.value?.id !== selectionId) return;
    productPropertyDetail.value = response.data;
  } catch (cause) {
    if (generation === productPropertyGeneration && primarySelection.value?.id === selectionId)
      productPropertyError.value = cause instanceof Error ? cause.message : '产品属性读取失败';
  } finally {
    if (generation === productPropertyGeneration) productPropertyLoading.value = false;
  }
}

async function loadSelectedMbdDetail(target: SelectionTarget) {
  const buildId = contract.value?.part_id;
  const revisionId = contract.value?.task_id;
  if (!buildId || !revisionId) return;
  const generation = ++mbdDetailGeneration;
  mbdAnnotationDetail.value = null;
  mbdNodeDetail.value = null;
  mbdRelations.value = [];
  mbdDetailLoading.value = true;
  mbdDetailError.value = '';
  try {
    if (target.kind === 'mbd_annotation') {
      const response = await fetchComponentBuildMbdAnnotationDetail(buildId, target.id, { silent: true });
      if (response.error || !response.data) throw response.error || new Error('标注详情不可用');
      if (generation !== mbdDetailGeneration || contract.value?.task_id !== revisionId ||
          primarySelection.value?.id !== target.id) return;
      mbdAnnotationDetail.value = response.data.annotation;
      mbdRelations.value = response.data.relations;
    } else {
      const response = await fetchComponentBuildMbdNodeDetail(buildId, target.id, { silent: true });
      if (response.error || !response.data) throw response.error || new Error('标注层级详情不可用');
      if (generation !== mbdDetailGeneration || contract.value?.task_id !== revisionId ||
          primarySelection.value?.id !== target.id) return;
      mbdNodeDetail.value = response.data.node;
      mbdRelations.value = response.data.relations;
    }
  } catch (cause) {
    if (generation === mbdDetailGeneration && primarySelection.value?.id === target.id)
      mbdDetailError.value = cause instanceof Error ? cause.message : '标注详情读取失败';
  } finally {
    if (generation === mbdDetailGeneration) mbdDetailLoading.value = false;
  }
}

async function loadSelectedRecognizedDetail(featureId: string) {
  const buildId = contract.value?.part_id;
  if (!buildId) return;
  const generation = ++recognizedDetailGeneration;
  recognizedDetailLoading.value = true;
  recognizedDetailError.value = '';
  try {
    const response = await fetchComponentBuildRecognizedFeatureDetail(buildId, featureId, { silent: true });
    if (response.error || !response.data) throw response.error || new Error('识别详情不可用');
    if (generation !== recognizedDetailGeneration || selectedFeatureId.value !== featureId || contract.value?.part_id !== buildId) return;
    const feature = response.data.feature as unknown as CanonicalFeatureRecord;
    const index = canonicalFeatures.value.findIndex(item => item.feature_center_id === featureId);
    if (index < 0) canonicalFeatures.value = [...canonicalFeatures.value, feature];
    else canonicalFeatures.value[index] = feature;
    measurements.value = response.data.measurements as unknown as MeasurementRecord[];
    const recognized = feature.typed_payload?.geometry_recognition as Record<string, unknown> | undefined;
    const combined = Array.isArray(recognized?.combined_measurements)
      ? recognized.combined_measurements as Array<Record<string, unknown>> : [];
    const relation = combined.find(item => item.status === 'measured' &&
      Array.isArray(item.start_point_mm) && Array.isArray(item.end_point_mm));
    if (relation) {
      activeRelationPoints = {
        a: relation.start_point_mm as number[],
        b: relation.end_point_mm as number[]
      };
      redrawRelationOverlay();
    }
  } catch (error) {
    if (generation === recognizedDetailGeneration && selectedFeatureId.value === featureId)
      recognizedDetailError.value = error instanceof Error ? error.message : '识别详情读取失败';
  } finally {
    if (generation === recognizedDetailGeneration) recognizedDetailLoading.value = false;
  }
}

function redrawRelationOverlay() {
  if (!activeRelationPoints) return;
  const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
  relationOverlay?.show({ status: 'success', operation: 'distance',
    values: { nearest_points: [activeRelationPoints] } }, color);
}

async function loadMoreRecognizedFeatures() {
  const buildId = contract.value?.part_id;
  const revisionId = contract.value?.task_id;
  const offset = recognizedNextOffset.value;
  if (!buildId || offset == null || recognizedPageLoading.value) return;
  recognizedPageLoading.value = true;
  try {
    const result = await fetchComponentBuildNativeEvidence<Record<string, unknown>>(
      buildId, 'canonical_features', offset, 100, { silent: true }
    );
    if (result.error || !result.data) throw result.error || new Error('识别特征列表读取失败');
    if (contract.value?.part_id !== buildId || contract.value?.task_id !== revisionId) return;
    const seen = new Set(canonicalFeatures.value.map(item => item.feature_center_id));
    canonicalFeatures.value = [...canonicalFeatures.value,
      ...(result.data.records as unknown as CanonicalFeatureRecord[]).filter(item => !seen.has(item.feature_center_id))];
    recognizedHasMore.value = result.data.has_more;
    recognizedNextOffset.value = result.data.next_offset;
    recognizedTotal.value = result.data.total;
    recognizedListError.value = '';
  } catch (error) {
    if (contract.value?.part_id === buildId && contract.value?.task_id === revisionId)
      recognizedListError.value = error instanceof Error ? error.message : '识别列表读取失败';
  } finally {
    recognizedPageLoading.value = false;
  }
}

async function loadSelectedNativeDetail(nodeId: string) {
  const buildId = contract.value?.part_id;
  const revisionId = contract.value?.task_id;
  if (!buildId || !revisionId) return;
  selectedNativeDetail.value = null;
  nativeDetailError.value = '';
  nativeDetailLoading.value = true;
  try {
    const detail = await nativeDetailLoader.load(buildId, revisionId, nodeId);
    if (detail && viewerSelection.value.primary?.kind === 'native_feature' &&
        viewerSelection.value.primary.id === nodeId && contract.value?.task_id === revisionId) {
      selectedNativeDetail.value = detail;
      nativeDetailLoading.value = false;
    }
  } catch (error) {
    if (viewerSelection.value.primary?.kind === 'native_feature' && viewerSelection.value.primary.id === nodeId) {
      nativeDetailError.value = error instanceof Error ? error.message : '数据库详情读取失败';
      nativeDetailLoading.value = false;
    }
  }
}

function projectSelectionForExistingTemplate() {
  const primary = viewerSelection.value.primary;
  const context = viewerSelection.value.context;
  const ids = projectSelectionIds(viewerSelection.value);
  selectedFeatureId.value = ids.recognizedFeatureId;
  selectedNativeFeatureId.value = ids.nativeFeatureId;
  selectedFaceId.value = ids.faceId;
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
  productPropertyGeneration += 1;
  productPropertyDetail.value = null;
  productPropertyLoading.value = false;
  productPropertyError.value = '';
  mbdDetailGeneration += 1;
  mbdAnnotationDetail.value = null;
  mbdNodeDetail.value = null;
  mbdRelations.value = [];
  mbdDetailLoading.value = false;
  mbdDetailError.value = '';
  recognizedDetailGeneration += 1;
  recognizedDetailLoading.value = false;
  recognizedDetailError.value = '';
  geometryDetailGeneration += 1;
  geometryDetailController?.abort();
  geometryDetail.value = null;
  geometryDetailLoading.value = false;
  geometryDetailError.value = '';
  nativeDetailLoader.cancel();
  selectedNativeDetail.value = null;
  nativeDetailError.value = '';
  nativeDetailLoading.value = false;
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
  const title = recognizedViewItems.value.find(item => item.featureId === featureId)?.title;
  selectionTarget.value = {
    source: 'catia',
    kind: 'feature',
    stableId: featureId,
    featureId,
    partId: contract.value?.part_id,
    displayName: title
  };
  selectTarget({ kind: 'recognized_feature', id: featureId, label: title, raw: feature }, 'recognized_feature');
}

function locateCurrentSelection() {
  if (!camera || !controls) return;
  const context = selectionContext.value;
  if (context.mappingStatus !== 'exact' && context.mappingStatus !== 'runtime_current_revision') return;
  const objects = [...new Set([
    ...context.primitiveIds.flatMap(id => primitiveObjects.get(id) || []),
    ...context.renderFaceIds.flatMap(id => faceObjects.get(id) || [])
  ])];
  if (focusCameraOnObjects(camera, controls, objects)) updateOrientationAxes();
}

function locateFeature(featureId: string) {
  if (primarySelection.value?.kind !== 'recognized_feature' || primarySelection.value.id !== featureId)
    selectFeature(featureId);
  locateCurrentSelection();
}

function selectMbdAnnotation(record: MbdAnnotationRecord) {
  selectTarget({ kind: 'mbd_annotation', id: record.fta_semantic_id, label: mbdAnnotationTitle(record), raw: record }, 'mbd');
}

function selectMbdNode(record: MbdNodeRecord) {
  const kind = record.pmi_kind === 'fta_view' ? 'mbd_view' :
    record.pmi_kind === 'fta_capture' ? 'mbd_capture' : 'mbd_set';
  selectTarget({ kind, id: record.pmi_id, label: mbdNodeTitle(record), raw: record }, 'mbd');
}

async function openMbdRelation(relation: MbdRelationRecord) {
  const targetId = primarySelection.value?.id === relation.pmi_id ? relation.target_id : relation.pmi_id;
  if (targetId === relation.target_id && relation.association_kind.includes('annotation')) {
    selectTarget({ kind: 'mbd_annotation', id: targetId, label: targetId }, 'mbd');
    return;
  }
  const buildId = contract.value?.part_id;
  if (!buildId) return;
  const revisionId = contract.value?.task_id;
  const response = await fetchComponentBuildMbdNodeDetail(buildId, targetId, { silent: true });
  if (contract.value?.task_id !== revisionId) return;
  if (response.data?.node) selectMbdNode(response.data.node);
  else mbdDetailError.value = '关联层级对象无法读取，请重试。';
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

async function loadNativeTreeChildren(node: FeatureTreeNode) {
  const buildId = contract.value?.part_id;
  if (!buildId || loadingNativeChildren.value.has(node.id)) return;
  const generation = nativeTreeGeneration;
  loadingNativeChildren.value.add(node.id);
  failedNativeChildren.value.delete(node.id);
  try {
    const fetchPage = async (parentId: string, offset: number) => {
      if (generation !== nativeTreeGeneration) throw new DOMException('Stale tree', 'AbortError');
      return loadCaaNewNativeChildPage(buildId, parentId, offset, {
        signal: assetRequestController.signal, silent: true
      });
    };
    for await (const children of nativeChildPages(node.id, fetchPage)) {
      if (generation !== nativeTreeGeneration) return;
      const merged = new Map(nativeFeatures.value.map(record => [record.feature_id, record]));
      children.forEach(record => merged.set(record.feature_id, record));
      nativeFeatures.value = [...merged.values()];
      await nextTick();
    }
  } catch (error) {
    if (generation === nativeTreeGeneration && !assetRequestController.signal.aborted) {
      failedNativeChildren.value.add(node.id);
      window.$message?.error(error instanceof Error ? error.message : '树节点加载失败，请重试');
    }
  } finally {
    if (generation === nativeTreeGeneration) loadingNativeChildren.value.delete(node.id);
  }
}

// 属性弹窗仅消费 PostgreSQL 接口；失败时不使用本地属性或文件兜底。
async function showNativeTreeNodeProperties(node: FeatureTreeNode) {
  selectNativeTreeNode(node);
  catiaPropertyNode.value = node;
  catiaPropertyApiTabs.value = null;
  catiaPropertyDialogOpen.value = false;
  const buildId = contract.value?.part_id;
  if (buildId) {
    try {
      const propertyResult = await loadCaaNewNodeProperties(buildId, node.id, {
        signal: assetRequestController.signal,
        silent: true
      });
      if (!propertyResult.tabs.length) {
        window.$message?.info('该节点没有可显示属性');
        return;
      }
      catiaPropertyApiTabs.value = apiTabsToCatiaTabs(propertyResult.tabs);
      if (!catiaPropertyApiTabs.value.length) {
        window.$message?.info('该节点没有可显示属性');
        return;
      }
      catiaPropertyTab.value = catiaPropertyApiTabs.value[0].name;
      catiaPropertyDialogOpen.value = true;
      return;
    } catch {
      catiaPropertyApiTabs.value = null;
      window.$message?.error('数据库属性读取失败，请重试');
      return;
    }
  }
  window.$message?.error('当前节点没有数据库版本，无法读取属性');
}

function selectBom(node: Api.ComponentBuild.ViewerBomNode) {
  selectBomSelection(node);
}

function selectBomSelection(node: Api.ComponentBuild.ViewerBomNode, canvasHit?: CadSelectionTarget) {
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
    objectUuid: canvasHit?.objectUuid,
    primitiveId: canvasHit?.primitiveId,
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
  selectTarget({ kind, id: node.node_id, label: node.name, instancePath: node.assembly_path,
    renderObjectUuid: canvasHit?.objectUuid, raw: node }, canvasHit ? 'canvas' : 'bom');
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
  selectTarget({ kind: 'face', id: faceId, label: faceId, namespace: 'step_render', raw: rawFace }, 'topology');
}

function selectGeometryTreeNode(item: TopologyExplorerItem) {
  selectionTarget.value = item.kind === 'face' ? {
    source: item.source === 'step_render' ? 'step' : 'catia',
    kind: 'face', stableId: item.entityId, faceId: item.entityId,
    partId: contract.value?.part_id, raw: item.raw
  } : null;
  selectTarget({ kind: item.kind, id: item.entityId, label: item.title,
    namespace: item.source, raw: item.raw }, 'topology');
}

function locateGeometryTreeNode(item: TopologyExplorerItem) {
  if (primarySelection.value?.kind !== item.kind || primarySelection.value.id !== item.entityId ||
      primarySelection.value.namespace !== item.source) selectGeometryTreeNode(item);
  locateCurrentSelection();
}

// 用途：统一计算选中、高亮、隔离、透明和剖切，不因侧栏响应式变化重置模型状态。
function applyVisualState() {
  const context = selectionContext.value;
  const trusted = context.mappingStatus === 'exact' || context.mappingStatus === 'runtime_current_revision';
  const candidatePreview = primarySelection.value?.kind === 'native_feature' && context.mappingStatus === 'candidate';
  const featureFaces = new Set([
    ...(featureMeshMap.value ? facesForFeature(featureMeshMap.value, selectedFeatureId.value) : []),
    ...(trusted || candidatePreview ? context.renderFaceIds : [])
  ]);
  const bomPrimitives = new Set(trusted || candidatePreview ? context.primitiveIds : []);
  const canvasObjects = new Set(context.renderObjectUuids);
  const wholePartPreview = primarySelection.value?.source === 'canvas' &&
    context.mappingAuthority === 'whole_part_preview';
  const hasSelection = featureFaces.size > 0 || bomPrimitives.size > 0 || canvasObjects.size > 0 || wholePartPreview;
  const primaryColor = themeStore.themeColor;
  const uncertain = Boolean(context.mappingStatus === 'candidate' ||
    (primarySelection.value?.kind === 'recognized_feature' &&
      (selectedRecognizedViewItem.value?.status.tone === 'warning' || selectedRecognizedViewItem.value?.candidatePreview)));
  const warningColor = getComputedStyle(document.documentElement).getPropertyValue('--el-color-warning').trim() || '#e6a23c';
  const highlightColor = normalizeCssColorForThree(uncertain ? warningColor : primaryColor);
  const overlayObjects: THREE.Mesh[] = [];
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
      wholePartPreview ||
      featureFaces.has(faceId) ||
      bomPrimitives.has(primitiveId) ||
      canvasObjects.has(object.uuid);
    if (active && !wholePartPreview &&
        ['face', 'recognized_feature', 'native_feature'].includes(primarySelection.value?.kind || ''))
      overlayObjects.push(object);
    const originalVisible = object.userData.cad_original_visible !== false;
    object.visible = originalVisible && (!isolated.value || !hasSelection || active);
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      const standard = material as THREE.MeshStandardMaterial;
      restoreMaterial(material);
      if (transparent.value) {
        standard.transparent = true;
        standard.opacity = hasSelection && active ? 0.94 : 0.2;
        standard.depthWrite = Boolean(hasSelection && active);
      }
      if (hasSelection && active && highlightColor) applySelectedMaterial(material, highlightColor, uncertain);
      standard.clippingPlanes = sectionEnabled.value ? [clippingPlane] : [];
      standard.needsUpdate = true;
    }
  }
  replaceSelectionSurfaceOverlay(selectionSurfaceOverlay, overlayObjects, highlightColor, uncertain,
    sectionEnabled.value ? [clippingPlane] : []);
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
    selectTarget({ kind: 'face', id: target.faceId, label: target.faceId,
      renderObjectUuid: target.objectUuid, raw: target.raw }, 'canvas');
    selectionTarget.value = target;
    return;
  }
  const root = contract.value?.bom.nodes[0];
  if (root) selectBomSelection(root, target);
  else {
    selectTarget({ kind: 'part', id: target.partId || 'CATPART', label: target.displayName,
      renderObjectUuid: target.objectUuid, raw: target.raw }, 'canvas');
    selectionTarget.value = target;
  }
}

// 用途：建立共享渲染环境；STEP 和 CATPart 只更换数据适配器，不创建第二套 Viewer。
function initViewer() {
  const container = containerRef.value;
  if (!container || scene) return;
  scene = new THREE.Scene();
  scene.add(selectionSurfaceOverlay);
  measurementOverlay = createMeasurementOverlay(scene);
  relationOverlay = createMeasurementOverlay(scene);
  tubePathOverlay = createTubePathOverlay(scene);
  sketchOverlay = createSketchOverlay(scene);
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

async function copyDetailValue(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    window.$message?.success('已复制');
  } catch {
    window.$message?.error('复制失败');
  }
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

watch(toolMode, applyToolMode);
watch([transparent, isolated, sectionEnabled, sectionOffset], applyVisualState);
watch(() => themeStore.themeColor, () => {
  applyVisualState();
  redrawRelationOverlay();
  if (measurementSession.result.value) {
    const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
    measurementOverlay?.show(measurementSession.result.value, color);
  }
});
onMounted(async () => {
  themeObserver = new MutationObserver(() => {
    applyVisualState();
    redrawRelationOverlay();
    if (measurementSession.result.value) {
      const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
      measurementOverlay?.show(measurementSession.result.value, color);
    }
    if (activeSketchPayload) {
      const color = getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary').trim() || '#409eff';
      sketchOverlay?.show(activeSketchPayload, color);
    }
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'style'] });
  const savedWidth = Number(window.localStorage.getItem('feature-center:navigation-width'));
  if (Number.isFinite(savedWidth)) navigationWidth.value = Math.min(460, Math.max(320, savedWidth));
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
  replaceSelectionSurfaceOverlay(selectionSurfaceOverlay, [], '', false);
  measurementSession.clear();
  measurementOverlay?.clear();
  relationOverlay?.clear();
  tubePathOverlay?.clear();
  sketchOverlay?.clear();
  geometryDetailController?.abort();
  nativeDetailLoader.clear();
  themeObserver?.disconnect();
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
        <span v-if="sourceFormat" class="format-badge">{{ sourceFormat === 'CATPRODUCT' ? 'CATProduct' : sourceFormat === 'CATPART' ? 'CATPart' : sourceFormat }}</span>
        <span v-if="contract?.bom.part_count">{{ contract.bom.part_count }} 个零件</span>
        <span v-if="contract?.summary.solid_count">{{ contract.summary.solid_count }} 个 Solid</span>
        <span v-if="isCatiaNativeSource(sourceFormat)">{{ contract?.summary.native_feature_count ?? 0 }} 条树记录</span>
        <span v-if="contract?.summary.native_definition_count != null">{{ contract.summary.native_definition_count }} 个原生定义，{{ contract.summary.native_typed_count ?? 0 }} 个专用解码</span>
        <span v-if="contract">{{ contract.summary.recognized_feature_count }} 个识别特征</span>
        <span v-if="contract" :class="mappingAvailable ? 'available' : 'muted'">
          Feature–Face {{ mappingAvailable ? '映射可用' : '映射不可用' }}
        </span>
        <span v-if="contract?.native_capture?.exact_brep_body_count != null && contract?.native_capture?.incomplete_brep_body_count != null &&
                    contract.native_capture.exact_brep_body_count + contract.native_capture.incomplete_brep_body_count > 0"
              :class="contract.native_capture.incomplete_brep_body_count ? 'muted' : 'available'"
              title="来自 PostgreSQL 中的 CAA 重建完整性结果">
          精确 B-Rep {{ contract.native_capture.exact_brep_body_count }}/{{
            contract.native_capture.exact_brep_body_count + contract.native_capture.incomplete_brep_body_count
          }} 体
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
        <button type="button" :disabled="!geometrySnapshot || sceneMode === 'explode'" :title="sceneMode === 'explode' ? '请先恢复原始装配位置' : !geometrySnapshot ? '当前版本没有可信 B-Rep 快照' : '打开测量'" @click="startMeasurement('distance')">测量</button>
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
          <div class="panel-scroll" :class="{ 'feature-tree-panel': activeTab === 'recognized', 'geometry-panel': activeTab === 'geometry', 'assembly-panel': activeTab === 'bom' && bomPanelMode === 'relations' }">
            <div v-if="activeTab === 'bom'" class="bom-panel-switch">
              <button type="button" :class="{ active: bomPanelMode === 'tree' }" @click="bomPanelMode = 'tree'">BOM</button>
              <button type="button" :class="{ active: bomPanelMode === 'relations' }" @click="bomPanelMode = 'relations'">装配关系</button>
            </div>
            <ElTree
              v-if="activeTab === 'bom' && bomPanelMode === 'tree' && contract?.bom.nodes.length"
              :data="contract.bom.nodes"
              node-key="node_id"
              :default-expanded-keys="bomDefaultExpandedKeys"
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
            <ElEmpty v-else-if="activeTab === 'bom' && bomPanelMode === 'tree'" description="当前文件没有装配 BOM" />
            <AssemblyRelationExplorer v-if="activeTab === 'bom' && bomPanelMode === 'relations'"
              :build-id="contract?.part_id || ''"
              :selected-id="primarySelection?.kind === 'assembly_relation' ? primarySelection.id : ''"
              @select="selectAssemblyRelation" />

            <div v-show="activeTab === 'recognized'" class="feature-tab-content">
              <div class="feature-source-tabs" :class="{ 'has-tube': tubeAvailable }">
                <button type="button" :class="{ active: featureSubTab === 'native' }" @click="featureSubTab = 'native'">
                  原生特征
                </button>
                <button type="button" :class="{ active: featureSubTab === 'mbd' }" @click="featureSubTab = 'mbd'">
                  MBD 标注
                </button>
                <button
                  type="button"
                  :class="{ active: featureSubTab === 'recognized' }"
                  @click="featureSubTab = 'recognized'"
                >
                  识别特征
                </button>
                <button v-if="tubeAvailable" type="button" :class="{ active: featureSubTab === 'tube' }"
                  @click="featureSubTab = 'tube'">导管</button>
              </div>
              <NativeFeatureTree
                v-show="featureSubTab === 'native'"
                :records="nativeFeatures"
                :source-file-name="contract?.summary.source_file_name || ''"
                :selected-id="selectedNativeTreeNodeId"
                :face-refs-by-feature-id="nativeFaceRefs"
                :parameter-values-by-object-id="nativeParameterValues"
                :loading-node-ids="loadingNativeChildren"
                :retry-node-ids="failedNativeChildren"
                @select="selectNativeTreeNode"
                @properties="showNativeTreeNodeProperties"
                @load-children="loadNativeTreeChildren"
              />
              <RecognizedFeatureExplorer v-show="featureSubTab === 'recognized'"
                :items="recognizedViewItems" :selected-id="primarySelection?.kind === 'recognized_feature' ? primarySelection.id : ''"
                :total="recognizedTotal" :has-more="recognizedHasMore" :loading="loading" :page-loading="recognizedPageLoading"
                :error="recognizedListError" :empty-description="recognizedEmptyDescription"
                @select="selectFeature" @locate="locateFeature" @load-more="loadMoreRecognizedFeatures"
                @retry="loadMoreRecognizedFeatures" />
              <MbdExplorer v-show="featureSubTab === 'mbd'"
                :build-id="featureSubTab === 'mbd' ? contract?.part_id || '' : ''"
                :revision-id="contract?.task_id || ''"
                :selected-id="primarySelection?.source === 'mbd' ? primarySelection.id : ''"
                @select-annotation="selectMbdAnnotation" @select-node="selectMbdNode" />
              <TubeExplorer v-show="featureSubTab === 'tube'" :build-id="contract?.part_id || ''"
                :selected-id="tubeSelection ? (tubeSelection.group === 'clearance'
                  ? (tubeSelection.record as TubeClearanceRecord).clearance_id
                  : (tubeSelection.record as TubePathRecord).path_id) : ''"
                @availability="tubeAvailable = $event" @select="selectTube" @recomputed="onTubeRecomputed" />
            </div>

            <TopologyExplorer v-if="activeTab === 'geometry'" :items="topologyExplorerModel.items"
              :diagnostics="topologyExplorerModel.diagnostics" :selected="primarySelection"
              :loading="loading" :error="topologyError" @select="selectGeometryTreeNode" @locate="locateGeometryTreeNode" />
          </div>
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
          <span v-else-if="selectedFeature">/ {{ selectedRecognizedViewItem?.title || selectedFeature.feature_center_id }}</span>
          <span v-else-if="selectedFace">/ {{ selectedFace.face_id }}</span>
        </div>
        <section ref="containerRef" class="viewer" />
        <ElEmpty
          v-if="!contract"
          class="viewer-empty"
          description="暂无 CATPart 解析结果，请从零件库打开已完成的 CATPart"
        />
        <ElEmpty
          v-else-if="!contract.viewer_asset"
          class="viewer-empty"
          description="该文件没有可用的轻量化几何，BOM、特征树和属性仍可正常浏览。"
        />
        <CadViewerControls
          v-if="contract && contract.viewer_asset"
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
        <AssemblyRelationDetail v-if="primarySelection?.kind === 'assembly_relation' && assemblySelection"
          :group="assemblySelection.group" :record="assemblySelection.record" />
        <TubeDetail v-else-if="primarySelection?.source === 'tube' && tubeSelection"
          :group="tubeSelection.group" :record="tubeSelection.record" :segment="tubeSelection.segment"
          :display-current="tubeSelection.displayCurrent" />
        <ObjectDetailPanel v-else
          :contract="contract"
          :source-format="sourceFormat"
          :selected-title="selectedTitle"
          :detail-layout="detailLayout"
          :primary-selection="primarySelection"
          :selection-context="selectionContext"
          :detail-node="detailNode"
          :detail-parent-node="detailParentNode"
          :selected-native-feature="selectedNativeFeature"
          :native-detail="selectedNativeDetail"
          :native-detail-loading="nativeDetailLoading"
          :native-detail-error="nativeDetailError"
          :selected-native-tree-node="selectedNativeTreeNode"
          :selected-native-tree-parent="selectedNativeTreeParent"
          :selected-native-parameter-family="selectedNativeParameterFamily"
          :selected-native-faces="selectedNativeFaces"
          :selected-feature="selectedFeature"
          :mbd-annotation="mbdAnnotationDetail"
          :mbd-node="mbdNodeDetail"
          :mbd-relations="mbdRelations"
          :mbd-detail-loading="mbdDetailLoading"
          :mbd-detail-error="mbdDetailError"
          :product-property-detail="productPropertyDetail"
          :product-property-loading="productPropertyLoading"
          :product-property-error="productPropertyError"
          :recognized-view-items="recognizedViewItems"
          :recognized-detail-loading="recognizedDetailLoading"
          :recognized-detail-error="recognizedDetailError"
          :selected-face="selectedFace"
          :face-feature-ids="faceFeatureIds"
          :selected-measurements="selectedMeasurements"
          :mapping-available="mappingAvailable"
          :isolated="isolated"
          :transparent="transparent"
          :geometry-detail="geometryDetail"
          :geometry-detail-loading="geometryDetailLoading"
          :geometry-detail-error="geometryDetailError"
          :measurement-operation="measurementSession.operation.value"
          :measurement-references="measurementSession.references.value"
          :measurement-result="measurementSession.result.value"
          :measurement-loading="measurementSession.loading.value"
          :measurement-error="measurementSession.error.value"
          :geometry-snapshot-available="Boolean(geometrySnapshot) && sceneMode !== 'explode'"
          :measurement-seed-point="measurementSeedPoint"
          :measurement-seed-points="measurementSession.seedPoints.value"
          @close="toggleDetails"
          @copy="copyDetailValue"
          @highlight="applyVisualState"
          @open-feature-links="openFeatureLinks"
          @open-native-face="openNativeFace"
          @open-mbd-relation="openMbdRelation"
          @retry-native-detail="primarySelection?.kind === 'native_feature' && loadSelectedNativeDetail(primarySelection.id)"
          @retry-recognized-detail="primarySelection?.kind === 'recognized_feature' && loadSelectedRecognizedDetail(primarySelection.id)"
          @toggle-isolated="isolated = !isolated"
          @toggle-transparent="transparent = !transparent"
          @start-measurement="startMeasurement"
          @calculate-measurement="calculateMeasurement"
          @clear-measurement="clearMeasurement"
          @show-native-sketch="showNativeSketch"
          @hide-native-sketch="hideNativeSketch"
        />
      </aside>
    </main>

    <ElDialog
      v-model="catiaPropertyDialogOpen"
      class="catia-property-dialog"
      width="min(88vw, 980px)"
      append-to-body
      :show-close="false"
    >
      <template #header>
        <header class="catia-property-header">
          <div class="catia-property-identity">
            <span class="catia-property-mark" aria-hidden="true">
              <ElIcon><Box /></ElIcon>
            </span>
            <h3>{{ catiaPropertyName }}</h3>
            <ElTag v-if="catiaPropertyType" class="catia-property-type" effect="plain">
              {{ catiaPropertyType }}
            </ElTag>
          </div>
          <ElButton class="catia-dialog-close" text circle aria-label="关闭" @click="catiaPropertyDialogOpen = false">
            <ElIcon><Close /></ElIcon>
          </ElButton>
        </header>
      </template>

      <ElTabs v-if="catiaPropertyTabs.length" v-model="catiaPropertyTab" class="catia-property-tabs">
        <ElTabPane v-for="tab in catiaPropertyTabs" :key="tab.name" :label="tab.label" :name="tab.name">
          <div class="catia-property-pane">
            <section v-if="tab.name === 'graphic'" class="catia-property-section">
              <h4>图形属性</h4>
              <div class="catia-property-card catia-property-card--three catia-property-card--graphic">
                <article
                  v-for="row in catiaGraphicRows(tab)"
                  :key="`graphic-${row.label}`"
                  class="catia-info-item"
                >
                  <ElIcon class="catia-info-icon"><component :is="iconForCatiaRow(row)" /></ElIcon>
                  <div class="catia-info-text">
                    <span>{{ row.label }}</span>
                    <strong :title="`${row.value}${displayUnit(row.unit)}`">
                      {{ row.value }}<small v-if="row.unit">{{ displayUnit(row.unit) }}</small>
                    </strong>
                  </div>
                </article>
              </div>
            </section>

            <section v-if="tab.name === 'product'" class="catia-property-section">
              <h4>部件信息</h4>
              <div class="catia-property-card catia-property-card--three">
                <article
                  v-for="row in catiaDisplayRows({ title: '部件信息', rows: [
                    { label: '实例名称', value: catiaRowValue(catiaGroupRows('product', '部件'), '实例名称') || '—' },
                    { label: '类型', value: catiaRowValue(catiaGroupRows('product', '部件'), 'StartUp') || catiaPropertyType || '—' },
                    { label: '内部名称', value: catiaRowValue(catiaGroupRows('product', '部件'), '内部名称') || catiaPropertyName }
                  ] })"
                  :key="`product-summary-${row.label}`"
                  class="catia-info-item"
                >
                  <ElIcon class="catia-info-icon"><component :is="iconForCatiaRow(row)" /></ElIcon>
                  <div class="catia-info-text">
                    <span>{{ row.label }}</span>
                    <strong :title="`${row.value}${displayUnit(row.unit)}`">
                      {{ row.value }}<small v-if="row.unit">{{ displayUnit(row.unit) }}</small>
                    </strong>
                  </div>
                </article>
              </div>
            </section>

            <section
              v-for="group in tab.groups.filter(item => tab.name !== 'graphic' && item.title !== '部件')"
              :key="group.title"
              class="catia-property-section"
            >
              <h4>
                {{ group.title === '产品' ? '产品信息' : group.title }}
                <small v-if="isInertiaGroup(group) && groupUnit(group)">{{ displayUnit(groupUnit(group)) }}</small>
              </h4>
              <div v-if="isInertiaGroup(group) && catiaDisplayRows(group).length" class="catia-inertia-table">
                <div class="catia-inertia-cell catia-inertia-head"></div>
                <div class="catia-inertia-cell catia-inertia-head">X</div>
                <div class="catia-inertia-cell catia-inertia-head">Y</div>
                <div class="catia-inertia-cell catia-inertia-head">Z</div>
                <template v-for="axis in ['X', 'Y', 'Z']" :key="`inertia-${axis}`">
                  <div class="catia-inertia-cell catia-inertia-head">{{ axis }}</div>
                  <div class="catia-inertia-cell">{{ inertiaCell(group.rows, axis, 'X') }}</div>
                  <div class="catia-inertia-cell">{{ inertiaCell(group.rows, axis, 'Y') }}</div>
                  <div class="catia-inertia-cell">{{ inertiaCell(group.rows, axis, 'Z') }}</div>
                </template>
              </div>
              <div
                v-else-if="catiaDisplayRows(group).length"
                class="catia-property-card"
                :class="{ 'catia-property-card--axis': group.title === '惯性中心' }"
              >
                <article v-for="row in catiaDisplayRows(group)" :key="`${group.title}-${row.label}`" class="catia-info-item">
                  <span v-if="isAxisRow(row)" class="catia-axis-badge" :class="`catia-axis-badge--${row.label.toLowerCase()}`">
                    {{ row.label.toUpperCase() }}
                  </span>
                  <ElIcon v-else class="catia-info-icon"><component :is="iconForCatiaRow(row)" /></ElIcon>
                  <div class="catia-info-text">
                    <span>{{ isAxisRow(row) ? row.label.toUpperCase() : row.label }}</span>
                    <ElTag v-if="shouldRenderCatiaStatus(row)" :type="isWarningStatus(row.value) ? 'warning' : 'success'" effect="light">
                      <ElIcon v-if="isWarningStatus(row.value)"><WarningFilled /></ElIcon>
                      {{ row.value }}
                    </ElTag>
                    <strong v-else :title="`${row.value}${displayUnit(row.unit)}`">
                      {{ row.value }}<small v-if="row.unit">{{ displayUnit(row.unit) }}</small>
                    </strong>
                  </div>
                </article>
              </div>
              <p v-else class="catia-property-empty">当前解析结果未提供</p>
            </section>
          </div>
        </ElTabPane>
      </ElTabs>
      <ElEmpty v-else description="当前节点没有可显示的 CATIA 属性" />
      <template #footer>
        <div class="catia-property-footer">
          <ElButton type="primary" @click="catiaPropertyDialogOpen = false">关闭</ElButton>
        </div>
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
  grid-template-columns: var(--navigation-width, 310px) minmax(0, 1fr) clamp(360px, 28vw, 420px);
  gap: 10px;
  transition: grid-template-columns 0.2s ease;
}
.workspace.bom-collapsed {
  grid-template-columns: 56px minmax(0, 1fr) clamp(360px, 28vw, 420px);
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
.navigation.collapsed .panel-heading,
.navigation.collapsed .semantic-tabs,
.navigation.collapsed .panel-scroll,
.navigation.collapsed .navigation-resizer {
  display: none;
}
.navigation.collapsed .rail-button {
  flex: 0 0 42px;
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
.panel-scroll {
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
.panel-scroll.geometry-panel {
  display: flex;
  overflow: hidden;
  padding: 0;
}
.panel-scroll.assembly-panel { display: flex; flex-direction: column; overflow: hidden; padding: 0; }
.bom-panel-switch { display: grid; grid-template-columns: 1fr 1fr; flex: none; gap: 4px; padding: 8px; }
.bom-panel-switch button { min-width: 0; padding: 7px; border-radius: 5px; color: var(--el-text-color-regular); }
.bom-panel-switch button.active { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.feature-tab-content {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}
.feature-source-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 3px;
  margin: 9px 10px 0;
  padding: 3px;
  border-radius: 7px;
  background: var(--el-fill-color-light);
}
.feature-source-tabs.has-tube { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.feature-source-tabs button {
  min-width: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  padding: 7px 2px;
  white-space: nowrap;
  cursor: pointer;
}
.feature-source-tabs button.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
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
.feature-group-title {
  margin: 5px 2px 9px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}
.viewer-shell {
  position: relative;
  background: var(--el-fill-color-light);
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
:global(.catia-property-dialog) {
  border-radius: 5px;
  background: var(--el-bg-color-overlay);
}
:global(.catia-property-dialog .el-dialog__header) {
  padding: 28px 28px 0;
}
:global(.catia-property-dialog .el-dialog__body) {
  min-height: min(62vh, 620px);
  padding: 28px 28px 0;
}
:global(.catia-property-dialog .el-dialog__footer) {
  padding: 24px 28px 28px;
}
.catia-property-header {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.catia-property-identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 16px;
}
.catia-property-mark {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  place-items: center;
  color: var(--el-color-primary);
}
.catia-property-mark .el-icon {
  font-size: 34px;
}
.catia-property-identity h3 {
  min-width: 0;
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.catia-property-type {
  max-width: 240px;
  height: 30px;
  border-color: var(--el-border-color);
  color: var(--el-text-color-regular);
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.catia-dialog-close {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  color: var(--el-text-color-primary);
}
.catia-dialog-close .el-icon {
  font-size: 26px;
}
.catia-dialog-close:hover,
.catia-dialog-close:focus-visible {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}
.catia-property-tabs {
  --el-tabs-header-height: 52px;
}
.catia-property-tabs :deep(.el-tabs__header) {
  margin: 0 0 26px;
}
.catia-property-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--el-border-color);
}
.catia-property-tabs :deep(.el-tabs__item) {
  height: 52px;
  padding: 0 28px;
  color: var(--el-text-color-primary);
  font-size: 20px;
  font-weight: 500;
}
.catia-property-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 700;
}
.catia-property-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  background: var(--el-color-primary);
}
.catia-property-pane {
  display: flex;
  min-height: 420px;
  flex-direction: column;
  gap: 28px;
}
.catia-property-section h4 {
  margin: 0 0 16px;
  color: var(--el-text-color-primary);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}
.catia-property-section h4 small {
  margin-left: 10px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  font-weight: 500;
}
.catia-property-card,
.catia-inertia-table {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--el-bg-color-overlay);
}
.catia-property-card {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  overflow: hidden;
}
.catia-property-card--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.catia-property-card--axis {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.catia-property-card--graphic .catia-info-item {
  min-height: 110px;
}
.catia-info-item {
  display: grid;
  min-width: 0;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
  padding: 22px 26px;
}
.catia-info-item + .catia-info-item {
  border-left: 1px solid var(--el-border-color);
}
.catia-property-card:not(.catia-property-card--three):not(.catia-property-card--axis) .catia-info-item:nth-child(2n + 1) {
  border-left: 0;
}
.catia-property-card:not(.catia-property-card--three):not(.catia-property-card--axis) .catia-info-item:nth-child(n + 3),
.catia-property-card--three .catia-info-item:nth-child(n + 4),
.catia-property-card--axis .catia-info-item:nth-child(n + 4) {
  border-top: 1px solid var(--el-border-color);
}
.catia-property-card--three .catia-info-item:nth-child(3n + 1),
.catia-property-card--axis .catia-info-item:nth-child(3n + 1) {
  border-left: 0;
}
.catia-info-icon {
  color: var(--el-text-color-primary);
  font-size: 30px;
}
.catia-axis-badge {
  display: grid;
  width: 34px;
  height: 34px;
  border: 1px solid currentcolor;
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  place-items: center;
}
.catia-axis-badge--x {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
.catia-axis-badge--y {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.catia-axis-badge--z {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.catia-info-text {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
  color: var(--el-text-color-regular);
  font-size: 16px;
}
.catia-info-text strong {
  min-width: 0;
  color: var(--el-text-color-primary);
  font-size: 20px;
  font-weight: 500;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.catia-info-text strong small {
  margin-left: 4px;
  font-size: 0.8em;
  font-weight: 500;
}
.catia-info-text .el-tag {
  width: fit-content;
  max-width: 100%;
  font-size: 14px;
}
.catia-info-text .el-icon {
  margin-right: 4px;
}
.catia-inertia-table {
  display: grid;
  grid-template-columns: 80px repeat(3, minmax(0, 1fr));
  overflow: hidden;
}
.catia-inertia-cell {
  min-width: 0;
  border-left: 1px solid var(--el-border-color-light);
  border-top: 1px solid var(--el-border-color-light);
  padding: 16px;
  color: var(--el-text-color-primary);
  font-family: Consolas, "Courier New", monospace;
  font-size: 17px;
  text-align: center;
}
.catia-inertia-cell:nth-child(-n + 4) {
  border-top: 0;
}
.catia-inertia-cell:nth-child(4n + 1) {
  border-left: 0;
}
.catia-inertia-head {
  background: var(--el-fill-color-lighter);
  font-family: inherit;
  font-weight: 500;
}
.catia-property-empty {
  display: flex;
  min-height: 108px;
  align-items: center;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  margin: 0;
  padding: 24px 32px;
  color: var(--el-text-color-secondary);
  font-size: 16px;
}
.catia-property-empty::before {
  content: "i";
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  border: 2px solid var(--el-text-color-secondary);
  border-radius: 50%;
  margin-right: 20px;
  color: var(--el-text-color-secondary);
  font-size: 26px;
  font-weight: 700;
  place-items: center;
}
.catia-property-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 24px;
  border-top: 1px solid var(--el-border-color);
  padding-top: 24px;
}
.catia-property-footer .el-button {
  min-width: 92px;
  height: 42px;
  font-size: 18px;
}
.details-trigger {
  display: none;
}
@media (max-width: 1439px) {
  .workspace {
    grid-template-columns: min(var(--navigation-width, 300px), 300px) minmax(0, 1fr) 360px;
  }
  .workspace.bom-collapsed {
    grid-template-columns: 54px minmax(0, 1fr) 360px;
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
    width: min(420px, calc(100vw - 40px));
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
