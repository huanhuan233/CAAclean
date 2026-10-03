import assert from 'node:assert/strict';
import test from 'node:test';
import * as detail from '../modules/object-detail-panel';
import {
  detailRowsFromRecord,
  formatDetailValue,
  geometryLinksFor,
  nativeFeatureRows,
  normalizeParameterRows,
  selectionEvidenceRows
} from '../modules/object-detail-panel';
import type { SelectionContext, SelectionTarget } from '../modules/viewer-selection';

test('详情值格式化保留 0、false 和空数组，只对空值显示占位', () => {
  assert.equal(formatDetailValue(0).text, '0');
  assert.equal(formatDetailValue(false).text, 'false');
  assert.equal(formatDetailValue([]).text, '[]');
  assert.equal(formatDetailValue(null).text, '—');
  assert.equal(formatDetailValue(undefined).text, '—');
});

test('参数集合支持对象和数组形态，并复制完整格式化值', () => {
  const objectRows = normalizeParameterRows({
    long_name: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    zero: 0,
    disabled: false,
    nested: { depth: 12 }
  });

  assert.deepEqual(
    objectRows.map(row => row.key),
    ['long_name', 'zero', 'disabled', 'nested']
  );
  assert.equal(objectRows[1].value.text, '0');
  assert.equal(objectRows[2].value.text, 'false');
  assert.equal(objectRows[3].value.text, '1 个字段');
  assert.match(objectRows[3].value.fullText, /"depth": 12/);

  const arrayRows = normalizeParameterRows([
    { key: 'length', value: 20 },
    { name: 'enabled', value: false },
    { label: 'material', value: null }
  ]);

  assert.deepEqual(
    arrayRows.map(row => row.key),
    ['length', 'enabled', 'material']
  );
  assert.equal(arrayRows[1].value.text, 'false');
  assert.equal(arrayRows[2].value.text, '—');
});

test('选择映射证据从 selection context 动态展开并保持新增字段可见', () => {
  const primary: SelectionTarget = { kind: 'native_feature', id: 'F000003', label: 'Pad.1' };
  const context = {
    mappingStatus: 'exact',
    mappingAuthority: 'native',
    primitiveIds: ['p0'],
    renderFaceIds: ['r1', 'r2'],
    nativeFaceIds: ['n1'],
    recognizedFeatureIds: [],
    nativeFeatureIds: ['F000003'],
    bomNodeIds: [],
    instanceIds: [],
    partIds: [],
    bodyIds: [],
    solidIds: [],
    loopIds: [],
    coedgeIds: [],
    edgeIds: [],
    vertexIds: [],
    diagnostics: ['from test'],
    backend_added_field: 'kept'
  } as SelectionContext & { backend_added_field: string };

  const rows = selectionEvidenceRows(primary, context);
  assert.equal(rows.find(row => row.key === 'primary_object')?.value.text, 'native_feature / F000003');
  assert.equal(rows.find(row => row.key === 'mappingStatus')?.value.text, '精确映射');
  assert.equal(rows.find(row => row.key === 'backend_added_field')?.value.text, 'kept');
});

test('特征详情按配置优先显示，并追加真实返回的未声明字段', () => {
  const rows = nativeFeatureRows({
    feature_id: 'F000001',
    native_type: 'Pad',
    update_status: 'up_to_date',
    native_feature_parameters: { length: 30 },
    children: [{ id: 'child' }],
    custom_backend_field: 'visible'
  } as never);

  assert.deepEqual(
    rows.slice(0, 3).map(row => row.key),
    ['feature_id', 'native_type', 'update_status']
  );
  assert.equal(
    rows.some(row => row.key === 'native_feature_parameters'),
    false
  );
  assert.equal(
    rows.some(row => row.key === 'children'),
    false
  );
  assert.equal(rows.find(row => row.key === 'custom_backend_field')?.value.text, 'visible');
});

test('通用记录行不会把对象直接渲染成 [object Object]', () => {
  const rows = detailRowsFromRecord({ id: 'face-1', bbox: { min: [0, 0, 0], max: [1, 1, 1] } });
  const bbox = rows.find(row => row.key === 'bbox');

  assert.equal(bbox?.value.text, '2 个字段');
  assert.notEqual(bbox?.value.fullText, '[object Object]');
});

test('关联几何沿用真实 face、feature 和边界数据', () => {
  const rows = geometryLinksFor({
    nativeFaceIds: ['NF1'],
    recognizedFaceIds: ['RF1'],
    faceFeatureIds: ['FC1'],
    selectedFace: { adjacent_face_ids: ['AF1'], boundary_edge_ids: ['E1'] }
  });

  assert.deepEqual(
    rows.map(row => `${row.kind}:${row.id}`),
    ['面:NF1', '面:RF1', '特征:FC1', '相邻面:AF1', '边:E1']
  );
});

test('数据库孔详情展开真实参数，保留零、false 与未知字段', () => {
  assert.equal(typeof detail.mergeNativeDetail, 'function');
  const feature = detail.mergeNativeDetail(
    { feature_id: 'occurrence_1', display_name: 'Hole.1', attributes: { object_id: 'object_7' } },
    { node_id: 'occurrence_1', revision_id: 'revision_A', object_id: 'object_7', native_feature_status: 'available',
      native_feature: { decoder_id: 'NativeHoleDecoder', decode_level: 'typed', decode_status: 'success',
        native_hole: { diameter_mm: 0, thread: { enabled: false, description: null }, custom_value: 'kept' } } }
  );
  const rows = detail.nativeSemanticParameterRows(feature);

  assert.equal(feature.decoder_id, 'NativeHoleDecoder');
  assert.equal(rows.find(row => row.key === 'diameter_mm')?.value.text, '0');
  assert.equal(rows.find(row => row.key === 'thread.enabled')?.value.text, 'false');
  assert.equal(rows.find(row => row.key === 'thread.description')?.value.text, '未采集 (null)');
  assert.equal(rows.find(row => row.key === 'custom_value')?.value.text, 'kept');
});

test('type_only 详情保留类型而不制造专用参数', () => {
  assert.equal(typeof detail.mergeNativeDetail, 'function');
  const feature = detail.mergeNativeDetail(
    { feature_id: 'occurrence_2', display_name: 'Fillet.1' },
    { node_id: 'occurrence_2', native_feature_status: 'available',
      native_feature: { decoder_id: 'NativeFilletDecoder', decode_level: 'type_only', payload_extraction_status: 'not_available' } }
  );
  assert.equal(feature.decode_level, 'type_only');
  assert.deepEqual(detail.nativeSemanticParameterRows(feature), []);
});

test('专用参数保留 null 与空字符串的不同含义', () => {
  const rows = detail.nativeSemanticParameterRows({
    feature_id: 'O1', native_feature_parameters: { head: { diameter_mm: null, description: '' } }
  });
  assert.equal(rows.find(row => row.key === 'head.diameter_mm')?.value.text, '未采集 (null)');
  assert.equal(rows.find(row => row.key === 'head.description')?.value.text, '空字符串');
});

test('属性事实读取失败不会显示成普通空值', () => {
  const field = { property_id: 'P1', key: 'diameter', display_name: '直径', raw_value: null,
    raw_unit: 'mm', display_value: null, display_unit: 'mm', value_type: 'number',
    source_api: 'CAA', read_status: 'failed', authority: 'native', display_order: 0, read_only: true };
  assert.equal(detail.nativePropertyValue(field).text, '读取失败');
  assert.equal(detail.nativePropertyValue({ ...field, read_status: 'success', display_value: '' }).text, '空字符串');
});
