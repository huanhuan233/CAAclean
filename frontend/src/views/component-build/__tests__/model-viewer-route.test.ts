import assert from 'node:assert/strict';
import test from 'node:test';
import { modelViewerLocation } from '../model-viewer-route';

// 用途：STEP 必须进入 CAD 模型解析，不能误进 CATPart 专属 Feature Center。
test('step opens cad model analysis route', () => {
  assert.deepEqual(modelViewerLocation('build-1', 'revision-1', 'STEP'), {
    path: '/cad-model',
    query: { build_id: 'build-1', revision_id: 'revision-1' }
  });
});

// 用途：CATPart 才进入 Feature Center，并由 build_id 获取受控 Bundle。
test('catpart opens feature center route', () => {
  assert.deepEqual(modelViewerLocation('build-2', 'revision-2', 'CATPART'), {
    path: '/feature-center',
    query: { build_id: 'build-2' }
  });
});
