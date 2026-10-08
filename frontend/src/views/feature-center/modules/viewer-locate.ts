import * as THREE from 'three';

type TargetControls = { target: THREE.Vector3; update: () => void };

/** Frame only the mapped finite meshes on an explicit Locate action. */
export function focusCameraOnObjects(
  camera: THREE.PerspectiveCamera,
  controls: TargetControls,
  objects: THREE.Object3D[]
): boolean {
  if (!objects.length) return false;
  const box = new THREE.Box3();
  for (const object of objects) box.expandByObject(object);
  if (box.isEmpty() || !Number.isFinite(box.min.x) || !Number.isFinite(box.max.x)) return false;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const direction = camera.position.clone().sub(controls.target).normalize();
  if (direction.lengthSq() === 0) direction.set(1, 1, 1).normalize();
  const fitHeight = size.length() / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
  const distance = Math.max(fitHeight * 1.2, 10);
  camera.position.copy(center).addScaledVector(direction, distance);
  camera.near = Math.max(distance / 10_000, 0.001);
  camera.far = Math.max(distance * 30, 100);
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
  return true;
}
