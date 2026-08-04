<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import {
  buildFaceToFeatureIndex,
  facesForFeature,
  parseJsonLines
} from './modules/feature-center-bundle';
import type { CanonicalFeatureRecord, FeatureMeshMap } from './modules/feature-center-bundle';
import { buildDetailPanelLayout } from './modules/detail-panel';
import type { DetailGroup } from './modules/detail-panel';
import NativeFeatureTree from './modules/NativeFeatureTree.vue';
import { buildNativeFeatureTree, flattenFeatureTree } from './modules/native-feature-tree';
import type { FeatureTreeNode, NativeFeatureRecord } from './modules/native-feature-tree';
import {
  readRecentFeatureCenterBuildId,
  resolveFeatureCenterBuildId,
  saveRecentFeatureCenterBuildId
} from './modules/recent-result';
import {
  defaultBomVisible,
  geometryDisplayId,
  tabsForSource,
  workerStageLabel
} from './modules/viewer-workspace';
import type { ViewerTab } from './modules/viewer-workspace';
import { fetchComponentBuildViewer, fetchComponentBuildViewerAsset, retryComponentBuild } from '@/service/api';

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

const route = useRoute();
const router = useRouter();
const assetRequestController = new AbortController();
const containerRef = ref<HTMLDivElement | null>(null);
const contract = ref<Api.ComponentBuild.ViewerContract | null>(null);
const canonicalFeatures = ref<CanonicalFeatureRecord[]>([]);
const nativeFeatures = ref<NativeFeatureRecord[]>([]);
const topologyFaces = ref<TopologyFaceRecord[]>([]);
const measurements = ref<MeasurementRecord[]>([]);
const featureMeshMap = ref<FeatureMeshMap | null>(null);
const faceMeshMap = ref<FaceMeshMap | null>(null);
const selectedFeatureId = ref('');
const selectedNativeFeatureId = ref('');
const selectedFaceId = ref('');
const selectedBomNode = ref<Api.ComponentBuild.ViewerBomNode | null>(null);
const faceFeatureIds = ref<string[]>([]);
const loading = ref(false);
const errorText = ref('');
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
const selectedBomPrimitiveIds = ref<string[]>([]);
const navigationWidth = ref(310);

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let modelRoot: THREE.Object3D | null = null;
let animationId = 0;
let resizeObserver: ResizeObserver | null = null;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const faceObjects = new Map<string, THREE.Mesh[]>();
const primitiveObjects = new Map<string, THREE.Mesh[]>();
const clippingPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
const workspaceStyle = computed(() => ({ '--navigation-width': `${navigationWidth.value}px` }));

// 用途：只展示真实契约中的格式；没有历史结果时保持空值，绝不伪造 CATPart 或 STEP 标签。
const sourceFormat = computed(() => contract.value?.source_format);
const sourceTabs = computed(() => tabsForSource('CATPART'));
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
  canonicalFeatures.value.forEach(feature => {
    feature.native_feature_ids.forEach(nativeId => {
      index[nativeId] = [...new Set([...(index[nativeId] || []), ...feature.geometry_refs.face_ids])];
    });
  });
  return index;
});
const nativeTreeNodes = computed(() => buildNativeFeatureTree(
  nativeFeatures.value,
  contract.value?.summary.source_file_name || '',
  nativeFaceRefs.value
));
const nativeTreeNodeIndex = computed(() => new Map(
  flattenFeatureTree(nativeTreeNodes.value).map(node => [node.id, node])
));
const selectedNativeTreeNode = computed(() => nativeTreeNodeIndex.value.get(selectedNativeFeatureId.value) ?? null);
const selectedNativeTreeParent = computed(() => {
  const parentId = selectedNativeTreeNode.value?.parentId;
  return parentId ? nativeTreeNodeIndex.value.get(parentId) ?? null : null;
});
const selectedNativeParameters = computed(() => Object.entries(selectedNativeFeature.value?.attributes || {}));
const selectedNativeFaces = computed(() => nativeFaceRefs.value[selectedNativeFeatureId.value] || []);
const filteredFaces = computed(() => {
  const keyword = geometryKeyword.value.trim().toLowerCase();
  const source = keyword
    ? topologyFaces.value.filter(item => `${item.face_id} ${item.surface_type ?? ''}`.toLowerCase().includes(keyword))
    : topologyFaces.value;
  return source.slice(0, geometryLimit.value);
});
const selectedTitle = computed(() =>
  selectedBomNode.value?.name
  || selectedNativeFeature.value?.display_name
  || selectedFeature.value?.subtype
  || selectedFace.value?.face_id
  || contract.value?.summary.model_name
  || ''
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
    featureFaceMappingAvailable: mappingAvailable.value
  });
});

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

// 用途：从特征关联面跳到几何拓扑并复用现有 Face 反查与 Viewer 高亮。
function openNativeFace(faceId: string) {
  activeTab.value = 'geometry';
  selectFace(faceId);
}

// 用途：从详情区进入特征列表；只有真实映射能力满足时按钮才会启用。
function openFeatureLinks() {
  if (!detailLayout.value.featureLinkEnabled) return;
  activeTab.value = 'recognized';
  featureSubTab.value = sourceFormat.value === 'CATPART' ? 'native' : 'recognized';
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

// 用途：在浏览器中复核 Manifest 记录的 SHA-256，损坏文件不会进入 Three.js。
async function sha256Buffer(buffer: ArrayBuffer) {
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
}

// 用途：加载 STEP/CATPart 共用 Viewer 契约；可选原生语义缺失时不影响真实 GLB 展示。
async function loadBuildBundle(buildId: string) {
  loading.value = true;
  errorText.value = '';
  try {
    const result = await fetchComponentBuildViewer(buildId, { signal: assetRequestController.signal, silent: true });
    if (result.error || !result.data) throw result.error || new Error('Viewer 契约不可用');
    if (result.data.source_format !== 'CATPART') {
      await router.replace({
        path: '/cad-model',
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
      throw new Error(result.data.error_message || `模型尚未就绪：${workerStageLabel(result.data.current_stage)}`);
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
    const [manifestBuffer, canonicalBuffer, measurementBuffer, nextFaceMapBuffer, featureMapBuffer, modelBuffer] = mandatoryBuffers;
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
      if (!expected || await sha256Buffer(buffer) !== expected) throw new Error(`Bundle 文件哈希不匹配：${relativePath}`);
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
    await loadOptionalSemanticAssets(result.data);
    clearSelection();
    saveRecentFeatureCenterBuildId(window.localStorage, buildId);
  } catch (error) {
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
    errorText.value = result.error instanceof Error ? result.error.message : '重试提交失败';
  } else {
    errorText.value = '';
    window.setTimeout(() => void loadBuildBundle(buildId), 800);
  }
  loading.value = false;
}

// 用途：并行读取原生 CAA Feature 与 B-Rep Face；缺失代表数据能力降级，不伪造内容。
async function loadOptionalSemanticAssets(viewerContract: Api.ComponentBuild.ViewerContract) {
  nativeFeatures.value = [];
  topologyFaces.value = [];
  const nativeUrl = viewerContract.native_semantics?.features_url;
  const facesUrl = viewerContract.feature_center.topology_faces_url;
  const requests: Promise<void>[] = [];
  if (nativeUrl) {
    requests.push(fetchAsset(nativeUrl).then(buffer => {
      nativeFeatures.value = parseJsonLines<NativeFeatureRecord>(new TextDecoder().decode(buffer));
    }));
  }
  if (facesUrl) {
    requests.push(fetchAsset(facesUrl).then(buffer => {
      topologyFaces.value = parseJsonLines<TopologyFaceRecord>(new TextDecoder().decode(buffer));
    }));
  }
  await Promise.all(requests);
}

// 用途：载入一次真实 GLB；BOM/详情栏显隐只触发 ResizeObserver，不重新调用本函数。
async function loadGlb(buffer: ArrayBuffer) {
  if (!scene) throw new Error('Viewer 尚未初始化');
  const gltf = await new Promise<Awaited<ReturnType<GLTFLoader['parseAsync']>>>((resolve, reject) => {
    new GLTFLoader().parse(buffer, '', resolve, reject);
  });
  if (modelRoot) scene.remove(modelRoot);
  disposeModel(modelRoot);
  faceObjects.clear();
  primitiveObjects.clear();
  modelRoot = gltf.scene;
  modelRoot.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const faceId = String(object.geometry.userData.face_id ?? object.userData.face_id ?? '');
    const primitiveId = String(object.geometry.userData.mesh_primitive_id ?? object.userData.mesh_primitive_id ?? '');
    if (faceId) {
      object.userData.face_id = faceId;
      (faceObjects.get(faceId) ?? faceObjects.set(faceId, []).get(faceId))?.push(object);
    }
    if (primitiveId) {
      object.userData.mesh_primitive_id = primitiveId;
      (primitiveObjects.get(primitiveId) ?? primitiveObjects.set(primitiveId, []).get(primitiveId))?.push(object);
    }
    const original = object.material;
    object.material = Array.isArray(original) ? original.map(item => item.clone()) : original.clone();
  });
  scene.add(modelRoot);
  fitCamera();
}

// 用途：清除语义选择但保持相机、透明、隔离和剖切状态。
function clearSelection() {
  selectedFeatureId.value = '';
  selectedNativeFeatureId.value = '';
  selectedFaceId.value = '';
  selectedBomNode.value = null;
  selectedBomPrimitiveIds.value = [];
  faceFeatureIds.value = [];
  applyVisualState();
}

// 用途：选择 Canonical Feature 后通过 feature_mesh_map 高亮真实面。
function selectFeature(featureId: string) {
  selectedFeatureId.value = featureId;
  selectedNativeFeatureId.value = '';
  selectedBomNode.value = null;
  selectedBomPrimitiveIds.value = [];
  selectedFaceId.value = '';
  applyVisualState();
}

// 用途：把 CAA 原生 Feature 关联到引用它的 Canonical Feature；无映射时如实保留选择。
function selectNativeFeature(feature: NativeFeatureRecord) {
  selectedNativeFeatureId.value = feature.feature_id;
  const linked = canonicalFeatures.value.find(item => item.native_feature_ids.includes(feature.feature_id));
  selectedFeatureId.value = linked?.feature_center_id ?? '';
  selectedBomNode.value = null;
  selectedBomPrimitiveIds.value = [];
  selectedFaceId.value = '';
  applyVisualState();
}

// 用途：规格树分组节点只参与导航；真实 Feature 节点继续复用原有选择和关联面高亮链路。
function selectNativeTreeNode(node: FeatureTreeNode) {
  if (node.raw) {
    selectNativeFeature(node.raw);
    return;
  }
  selectedNativeFeatureId.value = '';
  selectedFeatureId.value = '';
  selectedFaceId.value = '';
  applyVisualState();
}

// 用途：选择真实 BOM 节点并使用后端提供的 Primitive 映射；单零件根节点可代表完整模型。
function selectBom(node: Api.ComponentBuild.ViewerBomNode) {
  selectedBomNode.value = node;
  selectedBomPrimitiveIds.value = [...node.mesh_primitive_ids];
  selectedFeatureId.value = '';
  selectedNativeFeatureId.value = '';
  selectedFaceId.value = '';
  applyVisualState();
}

// 用途：选择拓扑 Face 后同步反查关联 Feature，并滚动语义页签。
function selectFace(faceId: string) {
  selectedFaceId.value = faceId;
  selectedBomNode.value = null;
  selectedBomPrimitiveIds.value = [];
  faceFeatureIds.value = featureMeshMap.value ? buildFaceToFeatureIndex(featureMeshMap.value)[faceId] ?? [] : [];
  selectedFeatureId.value = faceFeatureIds.value[0] ?? '';
  const linkedFeature = canonicalFeatures.value.find(item => item.feature_center_id === selectedFeatureId.value);
  selectedNativeFeatureId.value = linkedFeature?.native_feature_ids[0] ?? '';
  if (selectedNativeFeatureId.value) featureSubTab.value = 'native';
  applyVisualState();
}

// 用途：统一计算选中、高亮、隔离、透明和剖切，不因侧栏响应式变化重置模型状态。
function applyVisualState() {
  const featureFaces = new Set(featureMeshMap.value ? facesForFeature(featureMeshMap.value, selectedFeatureId.value) : []);
  const bomPrimitives = new Set(selectedBomPrimitiveIds.value);
  const wholeSinglePart = Boolean(selectedBomNode.value && contract.value?.bom.assembly_mode === 'single_part');
  const hasSelection = featureFaces.size > 0 || bomPrimitives.size > 0 || wholeSinglePart || Boolean(selectedFaceId.value);
  for (const [faceId, objects] of faceObjects.entries()) {
    for (const object of objects) {
      const primitiveId = String(object.userData.mesh_primitive_id ?? faceMeshMap.value?.faces[faceId]?.mesh_primitive_id ?? '');
      const active = wholeSinglePart || featureFaces.has(faceId) || faceId === selectedFaceId.value || bomPrimitives.has(primitiveId);
      object.visible = !isolated.value || !hasSelection || active;
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of materials) {
        const standard = material as THREE.MeshStandardMaterial;
        standard.color.set(active ? '#4f46e5' : '#bcc4cf');
        standard.emissive?.set(active ? '#312e81' : '#000000');
        standard.emissiveIntensity = active ? 0.28 : 0;
        standard.transparent = transparent.value;
        standard.opacity = transparent.value ? (active ? 0.92 : 0.2) : 1;
        standard.clippingPlanes = sectionEnabled.value ? [clippingPlane] : [];
        standard.needsUpdate = true;
      }
    }
  }
  clippingPlane.constant = sectionOffset.value;
}

// 用途：点击 GLB Primitive 后反选 Face 和关联 Feature；无映射时只显示真实 Face。
function handlePointer(event: PointerEvent) {
  if (!renderer || !camera) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects([...faceObjects.values()].flat(), false)[0];
  const faceId = String(hit?.object.userData.face_id ?? '');
  if (faceId) selectFace(faceId);
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
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight('#ffffff', '#64748b', 2.4));
  const light = new THREE.DirectionalLight('#ffffff', 2.6);
  light.position.set(1, 1, 2);
  scene.add(light);
  renderer.domElement.addEventListener('pointerdown', handlePointer);
  resizeObserver = new ResizeObserver(resizeViewer);
  resizeObserver.observe(container);
  resizeViewer();
  animate();
}

// 用途：按真实模型包围盒适应窗口，不写死参考图尺寸或相机位置。
function fitCamera() {
  if (!modelRoot || !camera || !controls) return;
  const box = new THREE.Box3().setFromObject(modelRoot);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const distance = Math.max(size.x, size.y, size.z, 1) * 1.8;
  camera.position.copy(center.clone().add(new THREE.Vector3(distance, distance, distance)));
  camera.near = Math.max(distance / 10_000, 0.001);
  camera.far = distance * 30;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
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
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(material => material.dispose());
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

function tabLabel(tab: ViewerTab) {
  return { bom: 'BOM 树', native: '原生特征', recognized: '特征', geometry: '几何拓扑' }[tab];
}

function faceTypeLabel(type: string | undefined) {
  return ({ plane: '平面', cylinder: '圆柱面', cone: '圆锥面', sphere: '球面', torus: '圆环面', bspline: 'B 样条面', bezier: 'Bezier 面' } as Record<string, string>)[type ?? ''] ?? type ?? '其他曲面';
}

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
  assetRequestController.abort();
  if (animationId) cancelAnimationFrame(animationId);
  resizeObserver?.disconnect();
  if (renderer) renderer.domElement.removeEventListener('pointerdown', handlePointer);
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
        <span v-if="sourceFormat" class="format-badge">CATPart</span>
        <span v-if="contract?.bom.part_count">{{ contract.bom.part_count }} 个零件</span>
        <span v-if="contract?.summary.solid_count">{{ contract.summary.solid_count }} 个 Solid</span>
        <span v-if="sourceFormat === 'CATPART'">{{ contract?.summary.native_feature_count ?? 0 }} 个原生特征</span>
        <span v-if="contract">{{ contract.summary.recognized_feature_count }} 个识别特征</span>
        <span v-if="contract" :class="mappingAvailable ? 'available' : 'muted'">Feature–Face {{ mappingAvailable ? '映射可用' : '映射不可用' }}</span>
        <span v-if="contract" class="stage-badge" :class="contract.status">{{ workerStageLabel(contract.current_stage) }}</span>
      </div>
      <div class="summary-actions">
        <button type="button" :disabled="!contract" @click="fitCamera">适应窗口</button>
        <button type="button" :disabled="!contract" :class="{ active: sectionEnabled }" @click="sectionEnabled = !sectionEnabled">剖切</button>
        <button type="button" disabled title="测量工作流尚未接入当前 Viewer">测量</button>
        <button type="button" class="details-trigger" @click="toggleDetails">详情</button>
      </div>
    </header>

    <div v-if="errorText" class="error-card">
      <strong>{{ contract?.source_format === 'CATPART' ? 'CATIA 处理未完成' : '模型处理未完成' }}</strong>
      <span>失败阶段：{{ workerStageLabel(contract?.current_stage) }}</span>
      <span v-if="contract?.error_code">错误码：{{ contract.error_code }}</span>
      <p>{{ errorText }}</p>
      <button v-if="route.query.build_id" type="button" @click="retryBuild">重试</button>
      <button v-if="route.query.build_id" type="button" @click="loadBuildBundle(String(route.query.build_id))">重新检查</button>
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
                <span class="tree-node"><span>{{ data.name }}</span><small v-if="data.quantity > 1">×{{ data.quantity }}</small></span>
              </template>
            </ElTree>
            <ElEmpty v-else-if="activeTab === 'bom'" description="当前文件没有装配 BOM" />

            <div v-show="activeTab === 'recognized'" class="feature-tab-content">
              <div class="feature-source-tabs">
                <button type="button" :class="{ active: featureSubTab === 'native' }" @click="featureSubTab = 'native'">原生特征</button>
                <button type="button" :class="{ active: featureSubTab === 'recognized' }" @click="featureSubTab = 'recognized'">识别特征</button>
              </div>
              <NativeFeatureTree
                v-show="featureSubTab === 'native'"
                :records="nativeFeatures"
                :source-file-name="contract?.summary.source_file_name || ''"
                :selected-id="selectedNativeFeatureId"
                :face-refs-by-feature-id="nativeFaceRefs"
                @select="selectNativeTreeNode"
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
                <ElEmpty v-if="!canonicalFeatures.length" description="暂无可信识别特征" />
              </div>
            </div>

            <template v-if="activeTab === 'geometry'">
              <ElInput v-model="geometryKeyword" clearable placeholder="搜索面编号或曲面类型" class="geometry-search" />
              <button
                v-for="(face, index) in filteredFaces"
                :key="face.face_id"
                type="button"
                class="list-card geometry-card"
                :class="{ active: selectedFaceId === face.face_id }"
                @click="selectFace(face.face_id)"
              >
                <strong>{{ geometryDisplayId('face', index) }} · {{ faceTypeLabel(face.surface_type) }}</strong>
                <span>面积 {{ face.area == null ? '—' : `${face.area.toFixed(3)} mm²` }}</span>
              </button>
              <button v-if="filteredFaces.length < topologyFaces.length" type="button" class="load-more" @click="geometryLimit += 160">继续加载</button>
              <ElEmpty v-if="!topologyFaces.length" description="没有可用的 B-Rep Face 索引" />
            </template>
          </div>
          <div v-if="contract?.bom.assembly_mode === 'single_part'" class="panel-hint">单零件模式自动隐藏 BOM</div>
          <div class="navigation-resizer" title="拖动调整侧栏宽度" @pointerdown="startNavigationResize" />
        </template>
        <template v-else>
          <button type="button" class="rail-button" :class="{ 'active-icon': activeTab === 'bom' }" title="BOM 树" aria-label="BOM 树" @click="activeTab = 'bom'; toggleBom()">
            <SvgIcon icon="lucide:network" />
          </button>
          <button type="button" class="rail-button" :class="{ 'active-icon': activeTab === 'recognized' }" title="特征" aria-label="特征" @click="activeTab = 'recognized'; toggleBom()">
            <SvgIcon icon="lucide:tags" />
          </button>
          <button type="button" class="rail-button" :class="{ 'active-icon': activeTab === 'geometry' }" title="几何拓扑" aria-label="几何拓扑" @click="activeTab = 'geometry'; toggleBom()">
            <SvgIcon icon="lucide:waypoints" />
          </button>
          <button type="button" class="rail-button primary" title="显示 BOM" aria-label="显示 BOM" @click="toggleBom">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>
          </button>
        </template>
      </aside>

      <section class="viewer-shell">
        <div v-if="contract" class="breadcrumb">
          <span>{{ contract.summary.model_name }}</span>
          <span v-if="selectedBomNode">/ {{ selectedBomNode.name }}</span>
          <span v-else-if="selectedNativeFeature">/ {{ selectedNativeFeature.display_name || selectedNativeFeature.feature_id }}</span>
          <span v-else-if="selectedFeature">/ {{ selectedFeature.subtype }}</span>
          <span v-else-if="selectedFace">/ {{ selectedFace.face_id }}</span>
        </div>
        <section ref="containerRef" class="viewer" />
        <ElEmpty
          v-if="!contract"
          class="viewer-empty"
          description="暂无 CATPart 解析结果，请从图元建库打开已完成的 CATPart"
        />
        <div v-if="contract" class="viewer-tools">
          <button type="button" @click="clearSelection">选择</button>
          <button type="button" @click="fitCamera">适应</button>
          <button type="button" :class="{ active: isolated }" @click="isolated = !isolated">隔离</button>
          <button type="button" :class="{ active: transparent }" @click="transparent = !transparent">透明</button>
          <button type="button" :class="{ active: sectionEnabled }" @click="sectionEnabled = !sectionEnabled">剖切</button>
        </div>
        <ElSlider v-if="contract && sectionEnabled" v-model="sectionOffset" class="section-slider" :min="-200" :max="200" />
      </section>

      <aside class="details" :class="{ open: detailsOpen }">
        <div class="panel-heading">
          <strong>对象详情</strong>
          <button type="button" @click="toggleDetails">×</button>
        </div>
        <div class="details-scroll">
          <div v-if="contract" class="object-card">
            <span class="object-icon">◇</span>
            <div><strong>{{ selectedTitle }}</strong><small>CATPart</small></div>
          </div>
          <section v-if="hasDetailGroup('part')" class="detail-section">
            <h4>零件属性</h4>
            <dl>
              <dt>零件号</dt><dd>{{ contract?.summary.part_number || detailNode?.part_number || '—' }}</dd>
              <dt>零件名称</dt><dd>{{ contract?.summary.part_name || detailNode?.name || '—' }}</dd>
              <dt>文件类型</dt><dd>{{ sourceFormat === 'CATPART' ? 'CATPart' : 'STEP' }}</dd>
              <dt>版本</dt><dd>{{ detailNode?.version || contract?.summary.version || '—' }}</dd>
              <template v-if="detailNode?.material || contract?.summary.material">
                <dt>材料</dt><dd>{{ detailNode?.material || contract?.summary.material }}</dd>
              </template>
            </dl>
          </section>
          <section v-if="hasDetailGroup('assembly_instance') && detailNode" class="detail-section">
            <h4>装配实例属性</h4>
            <dl>
              <dt>实例标识</dt><dd>{{ detailNode.instance_name || '—' }}</dd>
              <dt>所属组件</dt><dd>{{ detailParentNode?.name || '—' }}</dd>
              <dt>数量</dt><dd>{{ detailNode.quantity }}</dd>
              <dt>装配层级</dt><dd>{{ detailNode.level }}</dd>
              <dt>装配路径</dt><dd>{{ detailNode.assembly_path || '—' }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('assembly') && detailNode" class="detail-section">
            <h4>装配属性</h4>
            <dl>
              <dt>装配号</dt><dd>{{ detailNode.part_number || '—' }}</dd>
              <dt>装配名称</dt><dd>{{ detailNode.name }}</dd>
              <dt>类型</dt><dd>{{ detailNode.node_type === 'subassembly' ? '子装配' : '总装' }}</dd>
              <dt>子项数量</dt><dd>{{ detailNode.children.length }}</dd>
              <dt>装配层级</dt><dd>{{ detailNode.level }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('assembly_statistics') && detailNode" class="detail-section">
            <h4>装配统计</h4>
            <dl>
              <dt>直接子项</dt><dd>{{ detailNode.children.length }}</dd>
              <dt>Solid</dt><dd>{{ detailNode.solid_count || '—' }}</dd>
              <dt>体积</dt><dd>{{ detailNode.volume == null ? '—' : `${detailNode.volume} mm³` }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('source')" class="detail-section">
            <h4>{{ sourceFormat === 'CATPART' ? '来源与特征' : '来源与识别结果' }}</h4>
            <dl>
              <dt>源文件</dt><dd>{{ contract?.summary.source_file_name || '—' }}</dd>
              <template v-if="sourceFormat === 'CATPART'">
                <dt>原生特征</dt><dd>{{ contract?.native_semantics?.available ? contract.summary.native_feature_count : '不可用' }}</dd>
              </template>
              <dt>识别特征</dt><dd>{{ contract?.summary.recognized_feature_count ?? 0 }}</dd>
              <dt>Feature–Face 映射</dt><dd :class="mappingAvailable ? 'available' : 'muted'">{{ mappingAvailable ? '可用' : '不可用' }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('positioning') && detailNode" class="detail-section">
            <h4>装配定位</h4>
            <dl v-if="detailNode.instance_name || detailNode.constraint_status || detailNode.constraint_count != null">
              <dt>实例标识</dt><dd>{{ detailNode.instance_name || '—' }}</dd>
              <dt>约束状态</dt><dd>{{ detailNode.constraint_status || '未知' }}</dd>
              <dt v-if="detailNode.constraint_count != null">装配约束</dt><dd v-if="detailNode.constraint_count != null">{{ detailNode.constraint_count }}</dd>
            </dl>
            <p v-else class="muted">当前实例未提供定位数据</p>
          </section>
          <section v-if="hasDetailGroup('feature') && selectedNativeFeature" class="detail-section">
            <h4>特征详情</h4>
            <dl>
              <dt>名称</dt><dd>{{ selectedNativeTreeNode?.displayName || selectedNativeFeature.feature_id }}</dd>
              <dt>原生类型</dt><dd>{{ selectedNativeTreeNode?.nativeType || '未提供' }}</dd>
              <dt>所属容器</dt><dd>{{ selectedNativeTreeParent?.displayName || '未提供' }}</dd>
              <dt>建模顺序</dt><dd>{{ selectedNativeFeature.traversal_index ?? '未提供' }}</dd>
              <dt>更新状态</dt><dd>{{ selectedNativeFeature.update_status || '未提供' }}</dd>
            </dl>
            <h5>特征参数</h5>
            <dl v-if="selectedNativeParameters.length" class="parameter-list">
              <template v-for="entry in selectedNativeParameters" :key="entry[0]">
                <dt>{{ entry[0] }}</dt><dd>{{ formatNativeAttribute(entry[1]) }}</dd>
              </template>
            </dl>
            <p v-else class="muted">暂无可用参数</p>
            <h5>关联几何</h5>
            <div v-if="selectedNativeFaces.length" class="face-links">
              <button v-for="faceId in selectedNativeFaces" :key="faceId" type="button" @click="openNativeFace(faceId)">{{ faceId }}</button>
            </div>
            <p v-else class="muted">未建立关联面</p>
          </section>
          <section v-if="hasDetailGroup('feature') && selectedFeature" class="detail-section">
            <h4>特征属性</h4>
            <dl>
              <dt>识别类型</dt><dd>{{ selectedFeature.family }} / {{ selectedFeature.subtype }}</dd>
              <dt>复核状态</dt><dd>{{ selectedFeature.review_state }}</dd>
              <dt>关联面</dt><dd>{{ selectedFeature.geometry_refs.face_ids.join(', ') || '—' }}</dd>
              <dt>原生来源</dt><dd>{{ selectedFeature.native_feature_ids.join(', ') || '—' }}</dd>
            </dl>
          </section>
          <section v-if="hasDetailGroup('geometry') && selectedFace" class="detail-section">
            <h4>几何属性</h4>
            <dl>
              <dt>Face ID</dt><dd>{{ selectedFace.face_id }}</dd>
              <dt>曲面类型</dt><dd>{{ faceTypeLabel(selectedFace.surface_type) }}</dd>
              <dt>面积</dt><dd>{{ selectedFace.area == null ? '—' : `${selectedFace.area} mm²` }}</dd>
              <dt>关联特征</dt><dd>{{ faceFeatureIds.join(', ') || '无' }}</dd>
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
  </div>
</template>

<style scoped>
.feature-center-page { display: flex; height: calc(100vh - 112px); min-height: 620px; flex-direction: column; gap: 10px; color: var(--el-text-color-primary); }
button { border: 1px solid var(--el-border-color-light); border-radius: 7px; background: white; color: inherit; cursor: pointer; padding: 7px 11px; }
button:hover, button.active { border-color: var(--el-color-primary); color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
button:disabled { cursor: not-allowed; opacity: .45; }
.model-summary { display: flex; min-height: 54px; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color); padding: 4px 14px; }
.summary-main, .summary-actions { display: flex; min-width: 0; align-items: center; gap: 14px; flex-wrap: wrap; }
.summary-main strong { font-size: 17px; }
.summary-main span { font-size: 13px; white-space: nowrap; }
.format-badge, .stage-badge { border: 1px solid var(--el-color-primary-light-7); border-radius: 6px; color: var(--el-color-primary); padding: 4px 10px; }
.stage-badge.ready, .available { color: var(--el-color-success); }
.muted { color: var(--el-text-color-secondary); }
.error-card { display: flex; align-items: center; gap: 12px; border: 1px solid var(--el-color-danger-light-5); border-radius: 8px; background: var(--el-color-danger-light-9); padding: 10px 14px; }
.error-card p { min-width: 0; flex: 1; margin: 0; overflow-wrap: anywhere; }
.workspace { position: relative; display: grid; min-height: 0; flex: 1; grid-template-columns: var(--navigation-width, 310px) minmax(0, 1fr) 330px; gap: 10px; transition: grid-template-columns .2s ease; }
.workspace.bom-collapsed { grid-template-columns: 56px minmax(0, 1fr) 330px; }
.workspace.details-collapsed { grid-template-columns: var(--navigation-width, 310px) minmax(0, 1fr) 0; }
.workspace.bom-collapsed.details-collapsed { grid-template-columns: 56px minmax(0, 1fr) 0; }
.navigation, .viewer-shell, .details { min-width: 0; min-height: 0; border: 1px solid var(--el-border-color-light); border-radius: 9px; background: var(--el-bg-color); overflow: hidden; }
.navigation { position: relative; display: flex; flex-direction: column; }
.navigation.collapsed { align-items: center; padding: 10px 5px; gap: 10px; }
.panel-heading { display: flex; min-height: 48px; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--el-border-color-lighter); padding: 0 14px; }
.panel-heading button { border: 0; font-size: 20px; padding: 4px 8px; }
.semantic-tabs { display: grid; grid-template-columns: repeat(3, 1fr); border-bottom: 1px solid var(--el-border-color-lighter); }
.semantic-tabs button { border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: transparent; padding: 11px 4px; }
.semantic-tabs button.active { border-bottom-color: var(--el-color-primary); color: var(--el-color-primary); }
.panel-scroll, .details-scroll { min-height: 0; flex: 1; overflow: auto; padding: 10px; }
.panel-scroll.feature-tree-panel { display: flex; flex-direction: column; overflow: hidden; padding: 0; }
.feature-tab-content { display: flex; min-height: 0; flex: 1; flex-direction: column; }
.feature-source-tabs { display: grid; grid-template-columns: 1fr 1fr; border-bottom: 1px solid var(--el-border-color-lighter); padding: 0 10px; }
.feature-source-tabs button { border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: transparent; font-size: 12px; padding: 8px 4px; }
.feature-source-tabs button.active { border-bottom-color: var(--el-color-primary); color: var(--el-color-primary); }
.recognized-feature-list { min-height: 0; flex: 1; overflow: auto; padding: 10px; }
.panel-hint { border-top: 1px solid var(--el-border-color-lighter); color: var(--el-text-color-secondary); font-size: 12px; padding: 11px; }
.navigation-resizer { position: absolute; z-index: 3; top: 0; right: -2px; bottom: 0; width: 5px; cursor: col-resize; }
.navigation-resizer:hover { background: var(--el-color-primary-light-7); }
.tree-node { display: flex; width: 100%; justify-content: space-between; gap: 8px; }
.rail-button { display: grid; width: 42px; height: 42px; place-items: center; padding: 0; }
.rail-button svg { width: 22px; height: 22px; fill: none; stroke: currentcolor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.rail-button :deep(.svg-icon) { font-size: 21px; }
.rail-button.active-icon { border-color: var(--el-color-primary-light-7); color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.rail-button.primary { margin-top: 12px; }
.list-card { display: flex; width: 100%; flex-direction: column; align-items: flex-start; gap: 4px; margin-bottom: 7px; text-align: left; }
.list-card span { max-width: 100%; color: var(--el-text-color-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feature-group-title { margin: 5px 2px 9px; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 600; }
.geometry-search { margin-bottom: 10px; }
.load-more { width: 100%; }
.viewer-shell { position: relative; background: #f7f8fb; }
.viewer { position: absolute; inset: 0; }
.viewer-empty { position: absolute; z-index: 1; inset: 0; }
.breadcrumb { position: absolute; z-index: 2; top: 14px; left: 18px; display: flex; gap: 8px; border-radius: 7px; background: rgb(255 255 255 / 82%); padding: 7px 11px; backdrop-filter: blur(6px); }
.viewer-tools { position: absolute; z-index: 2; bottom: 58px; left: 50%; display: flex; gap: 4px; border: 1px solid var(--el-border-color-light); border-radius: 10px; background: rgb(255 255 255 / 92%); box-shadow: var(--el-box-shadow-light); padding: 7px; transform: translateX(-50%); }
.section-slider { position: absolute; z-index: 2; bottom: 18px; left: 50%; width: min(380px, 60%); transform: translateX(-50%); }
.details { display: flex; flex-direction: column; transition: opacity .15s ease; }
.details-collapsed .details { pointer-events: none; opacity: 0; }
.object-card { display: flex; align-items: center; gap: 12px; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 12px; }
.object-icon { color: var(--el-color-primary); font-size: 30px; }
.object-card div { display: flex; min-width: 0; flex-direction: column; }
.object-card small { color: var(--el-text-color-secondary); }
.detail-section { border-bottom: 1px solid var(--el-border-color-lighter); padding: 8px 0 12px; }
.detail-section h4 { margin: 7px 0 10px; }
.detail-section h5 { margin: 13px 0 8px; font-size: 13px; }
.detail-section dl { display: grid; grid-template-columns: 95px 1fr; gap: 8px; margin: 0; font-size: 13px; }
.detail-section dt { color: var(--el-text-color-secondary); }
.detail-section dd { margin: 0; overflow-wrap: anywhere; }
.parameter-list dd { white-space: pre-wrap; }
.face-links { display: flex; flex-wrap: wrap; gap: 5px; }
.face-links button { font-size: 12px; padding: 4px 7px; }
.actions { display: flex; flex-wrap: wrap; gap: 6px; }
.actions h4 { width: 100%; }
.actions .feature-link { width: 100%; margin-top: 2px; text-align: left; }
.advanced pre { max-height: 230px; overflow: auto; white-space: pre-wrap; font-size: 11px; }
.details-trigger { display: none; }
@media (max-width: 1439px) {
  .workspace { grid-template-columns: min(var(--navigation-width, 300px), 300px) minmax(0, 1fr) 290px; }
  .workspace.bom-collapsed { grid-template-columns: 54px minmax(0, 1fr) 290px; }
  .summary-main { gap: 9px; }
}
@media (max-width: 1179px) {
  .workspace, .workspace.bom-collapsed, .workspace.details-collapsed, .workspace.bom-collapsed.details-collapsed { grid-template-columns: 250px minmax(0, 1fr); }
  .workspace.bom-collapsed, .workspace.bom-collapsed.details-collapsed { grid-template-columns: 54px minmax(0, 1fr); }
  .details { position: absolute; z-index: 12; top: 70px; right: 10px; bottom: 10px; width: min(340px, calc(100vw - 40px)); box-shadow: var(--el-box-shadow-dark); transform: translateX(calc(100% + 24px)); transition: transform .2s ease; }
  .details.open { transform: translateX(0); }
  .details-trigger { display: inline-block; }
}
@media (max-width: 899px) {
  .feature-center-page { height: calc(100vh - 96px); min-height: 520px; }
  .model-summary { align-items: flex-start; flex-direction: column; padding: 8px 10px; }
  .summary-main span:not(.format-badge):not(.stage-badge) { display: none; }
  .workspace, .workspace.bom-collapsed, .workspace.details-collapsed, .workspace.bom-collapsed.details-collapsed { grid-template-columns: 54px minmax(0, 1fr); }
  .navigation:not(.collapsed) { position: absolute; z-index: 11; top: 118px; bottom: 10px; left: 10px; width: min(300px, calc(100vw - 40px)); box-shadow: var(--el-box-shadow-dark); }
  .viewer-tools { bottom: 20px; max-width: calc(100% - 24px); }
  .viewer-tools button { padding: 6px; }
}
</style>
