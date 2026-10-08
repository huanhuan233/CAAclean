import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from 'three';
import { createCompositeContourOverlay } from '../modules/composite-contour-overlay';

test('ordered ply contour overlays its own loops without becoming pickable model geometry', () => {
  const scene = new THREE.Scene();
  const overlay = createCompositeContourOverlay(scene);
  assert.equal(overlay.show({ status: 'derived_planar', loops: [{ role: 'outer', sampled_points_mm: [
    [0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]
  ] }] }, '#409eff'), true);
  const group = scene.children[0] as THREE.Group;
  assert.equal(group.userData.selection_overlay, true);
  assert.equal(group.children.length, 1);
  assert.equal((group.children[0] as THREE.Line).geometry.getAttribute('position').count, 5);
  overlay.clear();
  assert.equal(scene.children.length, 0);
});

test('unsupported or malformed contour does not create a misleading overlay', () => {
  const scene = new THREE.Scene();
  const overlay = createCompositeContourOverlay(scene);
  assert.equal(overlay.show({ status: 'unsupported', loops: [] }, '#409eff'), false);
  assert.equal(overlay.show({ status: 'derived_planar', loops: [{ role: 'outer', sampled_points_mm: [
    [0, 0, 0], [Number.NaN, 0, 0], [1, 1, 0]
  ] }] }, '#409eff'), false);
  assert.equal(scene.children.length, 0);
});
