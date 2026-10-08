import assert from 'node:assert/strict';
import test from 'node:test';
import { modelViewerLocation } from '../model-viewer-route';

// STEP 的查看动作应进入现有共用 Viewer，不能导航回当前零件库页面。
test('step opens shared feature center viewer', () => {
  assert.deepEqual(modelViewerLocation('build-1', 'revision-1', 'STEP'), {
    path: '/feature-center',
    query: { build_id: 'build-1' }
  });
});

// 用途：CATPart 才进入 Feature Center，并由 build_id 获取受控 Bundle。
test('catpart opens feature center route', () => {
  assert.deepEqual(modelViewerLocation('build-2', 'revision-2', 'CATPART'), {
    path: '/feature-center',
    query: { build_id: 'build-2' }
  });
});

test('catproduct opens feature center route', () => {
  assert.deepEqual(modelViewerLocation('build-3', 'revision-3', 'CATPRODUCT'), {
    path: '/feature-center',
    query: { build_id: 'build-3' }
  });
});
