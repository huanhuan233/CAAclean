import * as THREE from 'three';

/** Draw only the selected finite mesh surfaces, including hidden candidate walls. */
export function replaceSelectionSurfaceOverlay(
  root: THREE.Group,
  objects: THREE.Mesh[],
  color: string,
  uncertain: boolean,
  clippingPlanes: THREE.Plane[] = []
) {
  for (const child of [...root.children]) {
    root.remove(child);
    (child as THREE.Mesh).material && ((child as THREE.Mesh).material as THREE.Material).dispose();
  }
  for (const object of [...new Set(objects)]) {
    object.updateWorldMatrix(true, false);
    const preview = new THREE.Mesh(object.geometry, new THREE.MeshBasicMaterial({
      color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: uncertain ? 0.68 : 0.4,
      depthTest: !uncertain,
      depthWrite: false,
      clippingPlanes,
      polygonOffset: true,
      polygonOffsetFactor: -1
    }));
    preview.matrixAutoUpdate = false;
    preview.matrix.copy(object.matrixWorld);
    preview.renderOrder = 1000;
    preview.userData.pickable = false;
    root.add(preview);
  }
}
