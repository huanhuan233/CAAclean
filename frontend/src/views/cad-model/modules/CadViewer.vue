<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

defineOptions({
  name: 'CadViewer'
});

const props = defineProps<{
  meshes: Api.Cad.Mesh[];
  selectedFaceId?: string;
  highlightFaceIds?: string[];
}>();

const emit = defineEmits<{
  (e: 'faceClick', entityId: string): void;
}>();

const containerRef = ref<HTMLDivElement | null>(null);

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let animationId = 0;
let resizeObserver: ResizeObserver | null = null;

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const faceMeshes = new Map<string, THREE.Mesh>();

function createMaterial(entityId: string) {
  return new THREE.MeshStandardMaterial({
    color: colorForEntity(entityId),
    metalness: 0.12,
    roughness: 0.68,
    side: THREE.DoubleSide
  });
}

function colorForEntity(entityId: string) {
  const hue = Math.abs(hashCode(entityId)) % 360;
  return new THREE.Color(`hsl(${hue}, 42%, 58%)`);
}

function hashCode(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 100000;
  }
  return hash;
}

function initScene() {
  const container = containerRef.value;
  if (!container || scene) return;

  scene = new THREE.Scene();
  scene.background = new THREE.Color('#f7f9fc');

  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
  camera.position.set(180, 160, 220);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  const ambient = new THREE.HemisphereLight('#ffffff', '#b8c0cc', 2.4);
  scene.add(ambient);

  const keyLight = new THREE.DirectionalLight('#ffffff', 2.2);
  keyLight.position.set(120, 160, 220);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight('#dbeafe', 1);
  fillLight.position.set(-180, -80, 140);
  scene.add(fillLight);

  renderer.domElement.addEventListener('pointerdown', handlePointerDown);
  resizeObserver = new ResizeObserver(resizeViewer);
  resizeObserver.observe(container);
  resizeViewer();
  animate();
}

function animate() {
  if (!renderer || !scene || !camera) return;
  controls?.update();
  renderer.render(scene, camera);
  animationId = window.requestAnimationFrame(animate);
}

function resizeViewer() {
  const container = containerRef.value;
  if (!container || !renderer || !camera) return;
  const width = Math.max(container.clientWidth, 1);
  const height = Math.max(container.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function clearMeshes() {
  if (!scene) return;
  for (const mesh of faceMeshes.values()) {
    scene.remove(mesh);
    mesh.geometry.dispose();
    const material = mesh.material;
    if (Array.isArray(material)) {
      material.forEach(item => item.dispose());
    } else {
      material.dispose();
    }
  }
  faceMeshes.clear();
}

function buildGeometry(meshData: Api.Cad.Mesh) {
  const geometry = new THREE.BufferGeometry();
  const positions = meshData.positions.flat();
  const indices = meshData.indices.flat();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  if (meshData.normals?.length === meshData.positions.length) {
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(meshData.normals.flat(), 3));
  } else {
    geometry.computeVertexNormals();
  }
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function rebuildMeshes() {
  if (!scene) return;
  clearMeshes();

  for (const meshData of props.meshes) {
    if (meshData.positions.length && meshData.indices.length) {
      const material = createMaterial(meshData.entity_id);
      const mesh = new THREE.Mesh(buildGeometry(meshData), material);
      mesh.userData.entityId = meshData.entity_id;
      faceMeshes.set(meshData.entity_id, mesh);
      scene.add(mesh);
    }
  }

  fitToModel();
  applyHighlights();
}

function fitToModel() {
  if (!camera || !controls || faceMeshes.size === 0) return;
  const box = new THREE.Box3();
  for (const mesh of faceMeshes.values()) {
    box.expandByObject(mesh);
  }
  if (box.isEmpty()) return;

  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z, 1);
  const distance = maxSize / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2));

  camera.position.copy(center.clone().add(new THREE.Vector3(distance * 0.55, distance * 0.45, distance * 0.7)));
  camera.near = Math.max(distance / 1000, 0.01);
  camera.far = distance * 10;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function applyHighlights() {
  const highlightSet = new Set(props.highlightFaceIds ?? []);
  if (props.selectedFaceId) highlightSet.add(props.selectedFaceId);

  for (const [entityId, mesh] of faceMeshes.entries()) {
    const material = mesh.material as THREE.MeshStandardMaterial;
    const selected = entityId === props.selectedFaceId;
    const highlighted = highlightSet.has(entityId);
    if (selected) {
      material.color.set('#f97316');
      material.emissive.set('#7c2d12');
      material.emissiveIntensity = 0.3;
    } else if (highlighted) {
      material.color.set('#22c55e');
      material.emissive.set('#14532d');
      material.emissiveIntensity = 0.18;
    } else {
      material.color.copy(colorForEntity(entityId));
      material.emissive.set('#000000');
      material.emissiveIntensity = 0;
    }
    material.needsUpdate = true;
  }
}

function handlePointerDown(event: PointerEvent) {
  if (!renderer || !camera) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects([...faceMeshes.values()], false);
  const entityId = hits[0]?.object.userData.entityId;
  if (entityId) emit('faceClick', entityId);
}

function disposeViewer() {
  if (animationId) {
    window.cancelAnimationFrame(animationId);
    animationId = 0;
  }
  resizeObserver?.disconnect();
  resizeObserver = null;

  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
  }
  clearMeshes();
  controls?.dispose();
  controls = null;

  if (renderer) {
    renderer.dispose();
    renderer.domElement.remove();
    renderer = null;
  }
  scene = null;
  camera = null;
}

watch(
  () => props.meshes,
  () => {
    nextTick(rebuildMeshes).catch(() => undefined);
  },
  { deep: false }
);

watch(
  () => [props.selectedFaceId, props.highlightFaceIds?.join('|') ?? ''],
  () => applyHighlights()
);

onMounted(() => {
  initScene();
  rebuildMeshes();
});

onBeforeUnmount(() => {
  disposeViewer();
});
</script>

<template>
  <div ref="containerRef" class="cad-viewer">
    <div v-if="!meshes.length" class="viewer-empty">暂无可预览的 Face Mesh</div>
  </div>
</template>

<style scoped>
.cad-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 420px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: #f7f9fc;
}

.cad-viewer :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.viewer-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  pointer-events: none;
}
</style>
