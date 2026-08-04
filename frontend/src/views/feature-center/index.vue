<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import {
  buildFaceToFeatureIndex,
  facesForFeature,
  parseJsonLines
} from './modules/feature-center-bundle';
import type { CanonicalFeatureRecord, FeatureMeshMap } from './modules/feature-center-bundle';

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

const containerRef = ref<HTMLDivElement | null>(null);
const canonicalFeatures = ref<CanonicalFeatureRecord[]>([]);
const measurements = ref<MeasurementRecord[]>([]);
const featureMeshMap = ref<FeatureMeshMap | null>(null);
const selectedFeatureId = ref('');
const selectedFaceId = ref('');
const faceFeatureIds = ref<string[]>([]);
const loading = ref(false);
const errorText = ref('');
const transparent = ref(false);
const isolated = ref(false);
const sectionEnabled = ref(false);
const sectionOffset = ref(0);

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
const clippingPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);

const selectedFeature = computed(
  () => canonicalFeatures.value.find(item => item.feature_center_id === selectedFeatureId.value) ?? null
);
const selectedMeasurements = computed(() =>
  measurements.value.filter(item => item.feature_center_id === selectedFeatureId.value)
);

// 用途：在目录选择结果中按 Bundle 相对文件名查找文件，不依赖样件目录名称。
function normalizedFilePath(file: File) {
  return (file.webkitRelativePath || file.name).replace(/\\/gu, '/');
}

// 用途：只在同一个 Manifest 所在目录内按精确相对路径取文件，禁止跨 Bundle 混装证据。
function findBundleFile(files: File[], bundleRoot: string, relativePath: string) {
  const expected = bundleRoot ? `${bundleRoot}/${relativePath}` : relativePath;
  return files.find(file => normalizedFilePath(file) === expected);
}

// 用途：在浏览器中复核 Manifest 记录的 SHA-256，损坏文件不会进入 Viewer。
async function sha256Hex(file: File) {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
}

// 用途：加载一次完整 Bundle，并在所有必需文件验证后才替换当前模型。
async function handleBundleDirectory(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  const manifests = files.filter(file => normalizedFilePath(file).endsWith('/manifest.json') || file.name === 'manifest.json');
  if (manifests.length !== 1) {
    errorText.value = '所选目录必须且只能包含一个 Feature Center Manifest';
    return;
  }
  const manifestFile = manifests[0];
  const manifestPath = normalizedFilePath(manifestFile);
  const bundleRoot = manifestPath.includes('/') ? manifestPath.slice(0, manifestPath.lastIndexOf('/')) : '';
  const canonicalFile = findBundleFile(files, bundleRoot, 'canonical_features.jsonl');
  const measurementFile = findBundleFile(files, bundleRoot, 'measurements.jsonl');
  const featureMapFile = findBundleFile(files, bundleRoot, 'lightweight/feature_mesh_map.json');
  const modelFile = findBundleFile(files, bundleRoot, 'lightweight/model.glb');
  if (!canonicalFile || !measurementFile || !featureMapFile || !modelFile) {
    errorText.value = '所选目录不是完整的 Feature Center Bundle';
    return;
  }
  loading.value = true;
  errorText.value = '';
  try {
    const [manifestText, canonicalText, measurementText, featureMapText, modelBuffer] = await Promise.all([
      manifestFile.text(), canonicalFile.text(), measurementFile.text(), featureMapFile.text(), modelFile.arrayBuffer()
    ]);
    const manifest = JSON.parse(manifestText) as BundleManifest;
    if (manifest.schema_version !== 'cad_feature_center_v1') throw new Error('Feature Center Schema 不兼容');
    for (const [relativePath, file] of [
      ['canonical_features.jsonl', canonicalFile],
      ['measurements.jsonl', measurementFile],
      ['lightweight/feature_mesh_map.json', featureMapFile],
      ['lightweight/model.glb', modelFile]
    ] as const) {
      const expected = manifest.output_files[relativePath]?.sha256;
      if (!expected || await sha256Hex(file) !== expected) throw new Error(`Bundle 文件哈希不匹配：${relativePath}`);
    }
    const nextCanonical = parseJsonLines<CanonicalFeatureRecord>(canonicalText);
    const nextMeasurements = parseJsonLines<MeasurementRecord>(measurementText);
    const nextFeatureMap = JSON.parse(featureMapText) as FeatureMeshMap;
    if (nextFeatureMap.shape_hash !== manifest.brep.shape_hash) throw new Error('Mesh 映射与 B-Rep Shape Hash 不一致');
    await loadGlb(modelBuffer);
    canonicalFeatures.value = nextCanonical;
    measurements.value = nextMeasurements;
    featureMeshMap.value = nextFeatureMap;
    selectedFeatureId.value = nextCanonical[0]?.feature_center_id ?? '';
    selectedFaceId.value = '';
    faceFeatureIds.value = [];
    await nextTick();
    applyVisualState();
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : 'Bundle 加载失败';
  } finally {
    loading.value = false;
  }
}

// 用途：把 GLB ArrayBuffer 解析为 Three 场景，并登记每个 Primitive 携带的稳定 Face ID。
async function loadGlb(buffer: ArrayBuffer) {
  if (!scene) throw new Error('Viewer 尚未初始化');
  const gltf = await new Promise<Awaited<ReturnType<GLTFLoader['parseAsync']>>>((resolve, reject) => {
    new GLTFLoader().parse(buffer, '', resolve, reject);
  });
  if (modelRoot) scene.remove(modelRoot);
  disposeModel(modelRoot);
  faceObjects.clear();
  modelRoot = gltf.scene;
  modelRoot.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const faceId = String(object.geometry.userData.face_id ?? object.userData.face_id ?? '');
    if (!faceId) return;
    object.userData.face_id = faceId;
    const original = object.material;
    object.material = Array.isArray(original) ? original.map(item => item.clone()) : original.clone();
    (faceObjects.get(faceId) ?? faceObjects.set(faceId, []).get(faceId))?.push(object);
  });
  scene.add(modelRoot);
  fitCamera();
}

// 用途：选择 Canonical Feature 后只使用 feature_mesh_map 高亮真实 Face 集合。
function selectFeature(featureId: string) {
  selectedFeatureId.value = featureId;
  selectedFaceId.value = '';
  faceFeatureIds.value = [];
  applyVisualState();
}

// 用途：统一处理高亮、隔离、透明和剖切，恢复时重新使用每个面的原始颜色。
function applyVisualState() {
  const mapping = featureMeshMap.value;
  const highlighted = new Set(mapping ? facesForFeature(mapping, selectedFeatureId.value) : []);
  for (const [faceId, objects] of faceObjects.entries()) {
    const active = highlighted.has(faceId);
    for (const object of objects) {
      object.visible = !isolated.value || active;
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of materials) {
        const standard = material as THREE.MeshStandardMaterial;
        standard.color.set(active ? '#f97316' : '#aeb8c7');
        standard.emissive?.set(active ? '#7c2d12' : '#000000');
        standard.emissiveIntensity = active ? 0.25 : 0;
        standard.transparent = transparent.value;
        standard.opacity = transparent.value ? (active ? 0.9 : 0.22) : 1;
        standard.clippingPlanes = sectionEnabled.value ? [clippingPlane] : [];
        standard.needsUpdate = true;
      }
    }
  }
  clippingPlane.constant = sectionOffset.value;
}

// 用途：点击 Primitive 后读取 GLB extras.face_id，并通过反向索引展示所有关联 Feature。
function handlePointer(event: PointerEvent) {
  if (!renderer || !camera || !featureMeshMap.value) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1
  );
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects([...faceObjects.values()].flat(), false)[0];
  const faceId = String(hit?.object.userData.face_id ?? '');
  if (!faceId) return;
  selectedFaceId.value = faceId;
  faceFeatureIds.value = buildFaceToFeatureIndex(featureMeshMap.value)[faceId] ?? [];
  if (faceFeatureIds.value.length) {
    selectedFeatureId.value = faceFeatureIds.value[0];
    applyVisualState();
  }
}

// 用途：创建固定渲染环境；模型尺寸只影响自动相机，不改变几何坐标和单位。
function initViewer() {
  const container = containerRef.value;
  if (!container || scene) return;
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#f5f7fa');
  camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1_000_000);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.localClippingEnabled = true;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight('#ffffff', '#64748b', 2.2));
  const light = new THREE.DirectionalLight('#ffffff', 2.5);
  light.position.set(1, 1, 2);
  scene.add(light);
  renderer.domElement.addEventListener('pointerdown', handlePointer);
  resizeObserver = new ResizeObserver(resizeViewer);
  resizeObserver.observe(container);
  resizeViewer();
  animate();
}

// 用途：根据当前模型包围盒设置相机，不写死五孔样件尺寸或坐标。
function fitCamera() {
  if (!modelRoot || !camera || !controls) return;
  const box = new THREE.Box3().setFromObject(modelRoot);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const distance = Math.max(size.x, size.y, size.z, 1) * 2;
  camera.position.copy(center.clone().add(new THREE.Vector3(distance, distance, distance)));
  camera.near = Math.max(distance / 10_000, 0.001);
  camera.far = distance * 20;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

// 用途：使 WebGL 视口跟随容器大小，并保持相机投影比例正确。
function resizeViewer() {
  if (!containerRef.value || !renderer || !camera) return;
  const width = Math.max(containerRef.value.clientWidth, 1);
  const height = Math.max(containerRef.value.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

// 用途：持续更新阻尼控制和渲染，不改变 Bundle 的任何结构化数据。
function animate() {
  if (!renderer || !scene || !camera) return;
  controls?.update();
  renderer.render(scene, camera);
  animationId = requestAnimationFrame(animate);
}

// 用途：释放模型几何和材质，避免反复切换 Bundle 时占用显存。
function disposeModel(root: THREE.Object3D | null) {
  root?.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(material => material.dispose());
  });
}

watch([transparent, isolated, sectionEnabled, sectionOffset], applyVisualState);
onMounted(initViewer);
onBeforeUnmount(() => {
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
    <header class="toolbar">
      <label class="directory-button">
        加载 Feature Center Bundle
        <input type="file" webkitdirectory multiple @change="handleBundleDirectory" />
      </label>
      <ElSwitch v-model="transparent" active-text="透明" />
      <ElSwitch v-model="isolated" active-text="隔离所选特征" />
      <ElSwitch v-model="sectionEnabled" active-text="剖切" />
      <ElSlider v-if="sectionEnabled" v-model="sectionOffset" class="section-slider" :min="-200" :max="200" />
      <span v-if="errorText" class="error-text">{{ errorText }}</span>
    </header>

    <main v-loading="loading" class="workspace">
      <aside class="feature-list">
        <h3>Canonical Feature</h3>
        <button
          v-for="feature in canonicalFeatures"
          :key="feature.feature_center_id"
          type="button"
          :class="{ active: selectedFeatureId === feature.feature_center_id }"
          @click="selectFeature(feature.feature_center_id)"
        >
          <strong>{{ feature.family }} / {{ feature.subtype }}</strong>
          <span>{{ feature.feature_center_id }}</span>
          <span :class="feature.review_state">{{ feature.review_state }}</span>
        </button>
        <ElEmpty v-if="!canonicalFeatures.length" description="请选择 Bundle 目录" />
      </aside>

      <section ref="containerRef" class="viewer" />

      <aside class="details">
        <template v-if="selectedFeature">
          <h3>特征证据</h3>
          <dl>
            <dt>Feature Center ID</dt><dd>{{ selectedFeature.feature_center_id }}</dd>
            <dt>Native Feature</dt><dd>{{ selectedFeature.native_feature_ids.join(', ') }}</dd>
            <dt>Face</dt><dd>{{ selectedFeature.geometry_refs.face_ids.join(', ') }}</dd>
            <dt>复核状态</dt><dd>{{ selectedFeature.review_state }}</dd>
            <dt>来源</dt><dd>Native CAA + B-Rep Deterministic</dd>
          </dl>
          <h3>权威测量</h3>
          <div v-for="item in selectedMeasurements" :key="item.measurement_id" class="measurement">
            {{ item.name }}：{{ item.value ?? 'null' }} {{ item.unit }}<br />
            <small>{{ item.source }} / {{ item.method }} / {{ item.validity }}</small>
          </div>
        </template>
        <template v-if="selectedFaceId">
          <h3>拾取 Face</h3>
          <p>{{ selectedFaceId }}</p>
          <p>关联 Feature：{{ faceFeatureIds.join(', ') || '无' }}</p>
        </template>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.feature-center-page { display: flex; height: calc(100vh - 118px); min-height: 620px; flex-direction: column; gap: 10px; }
.toolbar { display: flex; align-items: center; gap: 16px; }
.directory-button { border-radius: 6px; background: var(--el-color-primary); color: white; cursor: pointer; padding: 8px 14px; }
.directory-button input { display: none; }
.section-slider { width: 220px; }
.error-text { color: var(--el-color-danger); }
.workspace { display: grid; min-height: 0; flex: 1; grid-template-columns: 280px minmax(420px, 1fr) 320px; gap: 10px; }
.feature-list, .details, .viewer { min-height: 0; overflow: auto; border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.feature-list, .details { padding: 12px; }
.feature-list button { display: flex; width: 100%; flex-direction: column; gap: 4px; margin-bottom: 8px; border: 1px solid transparent; border-radius: 6px; background: transparent; cursor: pointer; padding: 9px; text-align: left; }
.feature-list button:hover, .feature-list button.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.feature-list span { color: var(--el-text-color-secondary); font-size: 11px; overflow-wrap: anywhere; }
.feature-list .needs_review { color: var(--el-color-warning); }
.viewer { position: relative; background: #f5f7fa; }
.details dl { display: grid; grid-template-columns: 110px 1fr; gap: 7px; font-size: 12px; }
.details dt { color: var(--el-text-color-secondary); }
.details dd { margin: 0; overflow-wrap: anywhere; }
.measurement { margin-bottom: 10px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 8px; }
@media (max-width: 1000px) { .workspace { grid-template-columns: 220px 1fr; } .details { display: none; } }
</style>
