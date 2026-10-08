import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from 'three';
import { replaceSelectionSurfaceOverlay } from '../modules/selection-surface-overlay';

test('candidate overlay uses only mapped finite meshes and is not pickable', () => {
  const root = new THREE.Group();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 2), new THREE.MeshStandardMaterial());
  mesh.position.set(10, 0, 0);
  mesh.updateMatrixWorld(true);
  const clippingPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  replaceSelectionSurfaceOverlay(root, [mesh], '#e6a23c', true, [clippingPlane]);
  assert.equal(root.children.length, 1);
  const preview = root.children[0] as THREE.Mesh;
  assert.equal(preview.geometry, mesh.geometry);
  assert.equal(preview.userData.pickable, false);
  assert.equal(preview.matrix.elements[12], 10);
  assert.equal((preview.material as THREE.MeshBasicMaterial).depthTest, false);
  assert.equal((preview.material as THREE.MeshBasicMaterial).color.getHexString(), 'e6a23c');
  assert.equal((preview.material as THREE.MeshBasicMaterial).clippingPlanes?.[0], clippingPlane);
  replaceSelectionSurfaceOverlay(root, [], '#3366cc', false);
  assert.equal(root.children.length, 0);
});
