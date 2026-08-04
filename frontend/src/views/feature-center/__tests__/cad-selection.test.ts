import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from 'three';
import { registerCadPickables, resolveCadSelection } from '../modules/cad-selection';

test('GLB extras 中的真实 Face 与 Primitive 被注册为拾取索引', () => {
  const root = new THREE.Group();
  const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  mesh.userData.mesh_primitive_id = 'MP-1';
  root.add(mesh);
  const registration = registerCadPickables(root, { primitive_to_face: { 'MP-1': 'FACE-1' } });

  assert.equal(registration.pickables.length, 1);
  assert.equal(registration.faceObjects.get('FACE-1')?.[0], mesh);
  assert.equal(mesh.userData.face_id, 'FACE-1');
});

test('选面只使用稳定映射，不使用 Raycaster faceIndex', () => {
  const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  mesh.userData.mesh_primitive_id = 'MP-2';
  const target = resolveCadSelection(
    { object: mesh, faceIndex: 999 } as unknown as THREE.Intersection<THREE.Object3D>,
    'catia',
    { primitive_to_face: { 'MP-2': 'FACE-2' } },
    { partId: 'PART-1' }
  );

  assert.equal(target.kind, 'face');
  assert.equal(target.faceId, 'FACE-2');
  assert.notEqual(target.stableId, '999');
});

test('没有 Face 映射时如实降级为零件级选择', () => {
  const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  const target = resolveCadSelection(
    { object: mesh, faceIndex: 1 } as unknown as THREE.Intersection<THREE.Object3D>,
    'catia',
    null,
    { partId: 'PART-1', displayName: '测试零件' }
  );

  assert.equal(target.kind, 'part');
  assert.equal(target.stableId, 'PART-1');
});
