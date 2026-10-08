import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from 'three';
import { focusCameraOnObjects } from '../modules/viewer-locate';

test('explicit locate frames finite mapped geometry without changing view direction', () => {
  const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
  camera.position.set(100, 100, 100);
  const target = new THREE.Vector3();
  let updates = 0;
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 20, 30));
  mesh.position.set(40, 50, 60);
  const before = camera.position.clone().sub(target).normalize();
  assert.equal(focusCameraOnObjects(camera, { target, update: () => { updates += 1; } }, [mesh]), true);
  assert.deepEqual(target.toArray(), [40, 50, 60]);
  assert.ok(camera.position.clone().sub(target).normalize().distanceTo(before) < 1e-10);
  assert.equal(updates, 1);
  assert.equal(focusCameraOnObjects(camera, { target, update: () => {} }, []), false);
});
