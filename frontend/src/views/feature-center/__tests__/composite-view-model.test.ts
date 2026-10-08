import assert from 'node:assert/strict';
import test from 'node:test';
import type { CompositeStructureRecord } from '../../../service/api/cad';
import {
  compositeDetailKind, compositeFieldRows, compositeIdentityKey,
  compositeListItem, compositeMembers, compositeParentLinks,
  compositeType, formatCompositeField, formatCompositeNumber, updateStatus
} from '../modules/composite-view-model';

function record(kind: CompositeStructureRecord['kind'], id: string,
  overrides: Partial<CompositeStructureRecord> = {}): CompositeStructureRecord {
  return {
    object_id: id, kind, document_id: 'doc_1', display_name: `原始${id}`,
    update_status: 'up_to_date', occurrence_ids: ['occurrence_1'], occurrence_paths: [],
    parent_object_ids: [], ordered_child_object_ids: null, order_status: 'unavailable',
    fields: {}, diagnostics: [], ...overrides
  };
}

test('four native object kinds have distinct detail layouts and locked local icons', () => {
  const kinds = ['stacking', 'group', 'sequence', 'ply'] as const;
  assert.deepEqual(kinds.map(kind => compositeDetailKind(record(kind, kind))), kinds);
  assert.deepEqual(kinds.map(kind => compositeType(kind).icon), [
    'mdi:layers-triple-outline', 'mdi:folder-multiple-outline',
    'mdi:format-list-numbered', 'mdi:rhombus-outline'
  ]);
});

test('list identity is revision scoped while original name and ID remain untouched', () => {
  const row = record('ply', 'object_816', { display_name: '纸层.1',
    fields: { composite_orientation: { raw_value: 45, raw_unit: 'deg', normalized_value: 45,
      normalized_unit: 'deg', read_status: 'available' } } });
  const item = compositeListItem(row, 'revision-a');
  assert.equal(item.title, '单层 · 纸层.1');
  assert.equal(item.summary, '45°');
  assert.equal(item.objectId, 'object_816');
  assert.notEqual(item.key, compositeIdentityKey('revision-b', row));
  assert.match(item.searchText, /object_816.*纸层\.1|纸层\.1.*object_816/);
  assert.equal(row.display_name, '纸层.1');
});

test('known units format without changing raw precision, and zero or false are retained', () => {
  const area = { raw_value: 1.000000000000002, raw_unit: 'm²', normalized_value: 1000000.000000002,
    normalized_unit: 'mm²', read_status: 'available' };
  assert.equal(formatCompositeField(area).text, '1,000,000 mm²');
  assert.match(formatCompositeField(area).raw, /1\.000000000000002/);
  assert.equal(formatCompositeField({ ...area, raw_value: 0, normalized_value: 0, normalized_unit: 'deg' }).text, '0°');
  assert.equal(formatCompositeField({ ...area, raw_value: false, raw_unit: '', normalized_value: null }).text, '否');
  assert.equal(formatCompositeNumber(0.0000002), '0.0000002');
  assert.equal(formatCompositeField({ ...area, raw_value: '9007199254740993123', raw_unit: '', normalized_value: null }).text,
    '9007199254740993123');
  assert.equal(formatCompositeField({ ...area, raw_value: 1500, raw_unit: 'm^-3*kg', normalized_value: null }).text,
    '1,500 kg/m³');
});

test('unknown, stale, unmapped and native update states stay separate', () => {
  assert.equal(updateStatus('up_to_date').text, '原生对象已更新');
  assert.equal(updateStatus('not_up_to_date').text, '原生对象待更新');
  assert.equal(updateStatus('unexpected').text, '更新状态未知');
  const row = record('group', 'g', { update_status: 'not_up_to_date' });
  assert.equal(compositeListItem(row, 'r').orderText, '层序未取得');
  assert.equal(row.update_status, 'not_up_to_date');
});

test('ordered direct members keep native order and unresolved IDs remain visible', () => {
  const group = record('group', 'g', { order_status: 'native_complete',
    ordered_child_object_ids: ['s2', 's1', 'missing'] });
  const rows = [record('sequence', 's1'), record('sequence', 's2')];
  const members = compositeMembers(group, rows);
  assert.deepEqual(members.map(item => item.objectId), ['s2', 's1', 'missing']);
  assert.equal(members[2].title, '名称待加载');
  assert.equal(members[2].index, 3);
  assert.equal(members[2].unresolved, true);
  assert.equal(compositeMembers(record('stacking', 'empty'), []).length, 0);
});

test('parent links are parent links, not previous or next sequence guesses', () => {
  const sequence = record('sequence', 's1', { parent_object_ids: ['g'] });
  assert.deepEqual(compositeParentLinks(sequence, [record('group', 'g')]).map(link => link.objectId), ['g']);
  assert.equal(compositeMembers(sequence, []).length, 0);
  const group = record('group', 'g', { order_status: 'native_complete', ordered_child_object_ids: [] });
  const fallback = compositeMembers(group, [record('sequence', 's1', { parent_object_ids: ['g'] })]);
  assert.equal(fallback.length, 1);
  assert.equal(fallback[0].index, null);
});

test('ply fields are dedicated and unrecognized facts remain available for diagnostics', () => {
  const ply = record('ply', 'p', { fields: {
    composite_cured_thickness: { raw_value: 0.33, raw_unit: 'mm', normalized_value: 0.33,
      normalized_unit: 'mm', read_status: 'available' },
    unknown_native_value: { raw_value: 'original', raw_unit: '', normalized_value: null,
      normalized_unit: '', read_status: 'available' }
  } });
  assert.deepEqual(compositeFieldRows(ply, 'material').map(field => field.key), ['composite_cured_thickness']);
  assert.equal(ply.fields.unknown_native_value.raw_value, 'original');
});
