import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildFaceToFeatureIndex,
  facesForFeature,
  parseJsonLines
} from '../modules/feature-center-bundle';

// 用途：验证 Feature 列表选择能够通过 Bundle 映射得到真实 Face，而非名称或颜色猜测。
test('feature selection resolves stable face ids', () => {
  const mapping = {
    schema_version: 'feature_mesh_map_v1',
    shape_hash: 'shape',
    features: {
      FC1: { face_ids: ['FACE2', 'FACE1'], mesh_primitive_ids: ['P2', 'P1'] }
    }
  };

  assert.deepEqual(facesForFeature(mapping, 'FC1'), ['FACE1', 'FACE2']);
  assert.deepEqual(facesForFeature(mapping, 'missing'), []);
});

// 用途：验证点击 Face 可反查一个或多个 Canonical Feature，并保持稳定顺序。
test('face picking resolves every referenced feature', () => {
  const mapping = {
    schema_version: 'feature_mesh_map_v1',
    shape_hash: 'shape',
    features: {
      FC2: { face_ids: ['FACE1'], mesh_primitive_ids: ['P1'] },
      FC1: { face_ids: ['FACE1', 'FACE2'], mesh_primitive_ids: ['P1', 'P2'] }
    }
  };

  const index = buildFaceToFeatureIndex(mapping);

  assert.deepEqual(index.FACE1, ['FC1', 'FC2']);
  assert.deepEqual(index.FACE2, ['FC1']);
});

// 用途：验证浏览器加载 JSONL 时忽略空行并保留中文载荷。
test('jsonl parser preserves utf8 records', () => {
  assert.deepEqual(parseJsonLines<{ name: string }>(' {"name":"孔"}\n\n'), [{ name: '孔' }]);
});
