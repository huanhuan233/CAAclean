import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from 'three';
import { applySelectedMaterial, normalizeCssColorForThree, rememberMaterial, restoreMaterial } from '../modules/viewer-highlight-material';

test('modern CSS rgb theme variables become colors Three.js can parse', () => {
  assert.equal(normalizeCssColorForThree('rgb(250 173 20)'), '#faad14');
  assert.equal(normalizeCssColorForThree('rgb(6, 50, 246)'), '#0632f6');
  assert.equal(normalizeCssColorForThree('#0632F6'), '#0632F6');
});

test('candidate range uses visible yellow preview and restores original material', () => {
  const material = new THREE.MeshStandardMaterial({ color: '#808080', side: THREE.FrontSide, depthTest: true });
  rememberMaterial(material);
  applySelectedMaterial(material, '#e6a23c', true);
  assert.equal(material.color.getHexString(), 'e6a23c');
  assert.equal(material.side, THREE.DoubleSide);
  assert.equal(material.depthTest, false);
  assert.equal(material.depthWrite, false);
  assert.equal(material.transparent, true);
  restoreMaterial(material);
  assert.equal(material.color.getHexString(), '808080');
  assert.equal(material.side, THREE.FrontSide);
  assert.equal(material.depthTest, true);
  assert.equal(material.depthWrite, true);
  assert.equal(material.transparent, false);
});

test('verified range keeps normal depth behavior with theme color', () => {
  const material = new THREE.MeshStandardMaterial({ color: '#808080' });
  rememberMaterial(material);
  applySelectedMaterial(material, '#3366cc', false);
  assert.equal(material.color.getHexString(), '3366cc');
  assert.equal(material.side, THREE.FrontSide);
  assert.equal(material.depthTest, true);
  restoreMaterial(material);
});
