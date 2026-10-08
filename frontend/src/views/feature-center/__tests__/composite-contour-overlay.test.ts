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

test('nominal direction arrow is a disposable preview and never model geometry', () => {
  const scene = new THREE.Scene();
  const overlay = createCompositeContourOverlay(scene);
  const region = { status: 'derived_planar', loops: [{ role: 'outer', sampled_points_mm: [
    [0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]
  ] }] };
  assert.equal(overlay.show(region, '#409eff', { status: 'derived_planar_nominal', vector: [0, 1, 0] }), true);
  assert.equal((scene.children[0] as THREE.Group).children.length, 2);
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

test('published planar region mesh is separately pickable without entering model pickables', () => {
  const scene = new THREE.Scene();
  const overlay = createCompositeContourOverlay(scene);
  assert.equal(overlay.showCoverage([{ region_id: 'region_1', display_vertices_mm: [
    [0, 0, 0], [10, 0, 0], [0, 10, 0]
  ], display_triangles: [[0, 1, 2]] }], '#409eff'), true);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(2, 2, 10);
  camera.lookAt(2, 2, 0);
  camera.updateMatrixWorld();
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
  assert.equal(overlay.pickRegion(raycaster), 'region_1');
  overlay.clear();
  assert.equal(overlay.pickRegion(raycaster), null);
});
