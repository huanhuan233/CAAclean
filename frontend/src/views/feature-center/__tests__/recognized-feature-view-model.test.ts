import assert from 'node:assert/strict';
import test from 'node:test';
import { buildRecognizedFeatureItems, filterRecognizedFeatureItems } from '../modules/recognized-feature-view-model';
import type { CanonicalFeatureRecord, FeatureMeshMap } from '../modules/feature-center-bundle';

// 测试夹具保留原始 family/subtype 参数，便于逐项核对后端枚举。
// eslint-disable-next-line max-params
function feature(
  id: string,
  family: string,
  subtype: string,
  options: { reviewState?: string; payload?: object } = {}
): CanonicalFeatureRecord {
  return {
    feature_center_id: id,
    family,
    subtype,
    review_state: options.reviewState || 'auto_verified',
    geometry_refs: { face_ids: ['face-1'] },
    native_feature_ids: [],
    typed_payload: { geometry_recognition: options.payload || {} },
    provenance: {}
  };
}

const mapping: FeatureMeshMap = {
  schema_version: '1',
  shape_hash: 'shape-A',
  features: {
    'FC-1': { face_ids: ['face-1'], mesh_primitive_ids: ['primitive-1'] },
    'FC-2': { face_ids: ['face-2'], mesh_primitive_ids: ['primitive-2'] }
  }
};

test('已知名称、状态和有限范围来自独立证据，原始枚举保持不变', () => {
  const fillet = feature('FC-1', 'fillet', 'constant_radius_straight_edge', {
    payload: {
      classification_status: 'confirmed',
      cavity_role_status: 'candidate',
      render_range_status: 'confirmed'
    }
  });
  const web = feature('FC-2', 'web', 'thin_plate_candidate', {
    reviewState: 'needs_review',
    payload: {
      structural_role_status: 'candidate',
      local_thickness_mm: 3,
      render_range_status: 'candidate_full_opposed_faces'
    }
  });
  const items = buildRecognizedFeatureItems([fillet, web], 'revision-A', mapping);
  assert.equal(items[0].title, '圆角 001');
  assert.deepEqual(items[0].descriptors, ['恒定半径', '直边']);
  assert.equal(items[0].status.label, '自动核验');
  assert.equal(items[0].canLocate, true);
  assert.equal(items[1].title, '薄板候选 001');
  assert.equal(items[1].status.label, '待复核');
  assert.equal(items[1].canLocate, true);
  assert.equal(items[1].candidatePreview, true);
  assert.equal(items[1].descriptors.includes('等厚'), false);
  assert.equal(fillet.subtype, 'constant_radius_straight_edge');
  assert.equal(web.review_state, 'needs_review');
});

test('孔、P4 类别及未知类型保留候选含义并可搜索原始枚举', () => {
  const records = [
    feature('H1', 'hole', 'through_hole'),
    feature('H2', 'hole', 'cylindrical_void_candidate', {
      reviewState: 'needs_review'
    }),
    feature('B1', 'boss', 'circular_straight_wall'),
    feature('P1', 'pocket', 'rectangular_straight_wall'),
    feature('S1', 'slot', 'open_straight_wall'),
    feature('R1', 'rib', 'straight_prismatic_candidate', {
      reviewState: 'needs_review'
    }),
    feature('F1', 'flange', 'straight_free_edge_band_candidate', {
      reviewState: 'needs_review'
    }),
    feature('X1', 'alien', 'mystery'),
    feature('C1', 'chamfer', 'unknown_mode')
  ];
  const items = buildRecognizedFeatureItems(records, 'rev', null);
  assert.deepEqual(
    items.map(item => item.name),
    ['圆孔', '圆柱空域候选', '圆形凸台', '矩形型腔', '开放槽', '直筋候选', '缘条候选', '未分类特征', '倒角']
  );
  assert.deepEqual(items[8].descriptors, ['其他子类型']);
  assert.deepEqual(
    filterRecognizedFeatureItems(items, {
      category: 'all',
      status: 'all',
      keyword: 'cylindrical_void_candidate'
    }).map(item => item.featureId),
    ['H2']
  );
  assert.deepEqual(
    filterRecognizedFeatureItems(items, {
      category: 'hole',
      status: 'all',
      keyword: '圆孔'
    }).map(item => item.featureId),
    ['H1']
  );
  assert.equal(items[7].featureId, 'X1');
});

test('搜索、筛选、追加和版本切换不改变当前结果内已有序号和真实 ID', () => {
  const records = [
    feature('A', 'fillet', 'constant_radius_straight_edge'),
    feature('B', 'fillet', 'constant_radius_straight_edge')
  ];
  const before = buildRecognizedFeatureItems(records, 'revision-A', mapping);
  const after = buildRecognizedFeatureItems(
    [...records, feature('C', 'fillet', 'constant_radius_straight_edge')],
    'revision-A',
    mapping
  );
  assert.deepEqual(
    after.map(item => item.title),
    ['圆角 001', '圆角 002', '圆角 003']
  );
  assert.equal(
    filterRecognizedFeatureItems(after, {
      category: 'fillet',
      status: 'all',
      keyword: 'B'
    })[0].title,
    '圆角 002'
  );
  assert.equal(before[0].key, after[0].key);
  assert.notEqual(before[0].key, buildRecognizedFeatureItems(records, 'revision-B', mapping)[0].key);
  assert.notEqual(
    before[0].key,
    buildRecognizedFeatureItems(records, 'revision-A', {
      ...mapping,
      shape_hash: 'shape-B'
    })[0].key
  );
});

test('矛盾状态保持保守，不用有效测量升级结构角色', () => {
  const record = feature('R', 'rib', 'straight_prismatic_candidate', {
    payload: {
      classification_status: 'confirmed',
      structural_role_status: 'candidate',
      local_thickness_mm: 2
    }
  });
  const item = buildRecognizedFeatureItems([record], 'revision', null)[0];
  assert.equal(item.status.label, '状态需核实');
  assert.equal(item.name, '直筋候选');
  assert.equal(item.canLocate, false);
  const hole = feature('H', 'hole', 'cylindrical_void_candidate', {
    payload: { render_range_status: 'candidate' }
  });
  const candidate = buildRecognizedFeatureItems([hole], 'revision', null)[0];
  assert.equal(candidate.name, '圆柱空域候选');
  assert.equal(candidate.status.label, '状态需核实');
});
