import assert from 'node:assert/strict';
import test from 'node:test';
import { adaptNativeTopologyRecord, buildTopologyItems, filterTopologyItems, preferMappedTopologyFaces, sameTopologySelection } from '../modules/topology-view-model';
import { resolveViewerSelection } from '../modules/viewer-selection';
import type { TopologyCategory, TopologyInput } from '../modules/topology-view-model';

test('20 coedges under one body retain 20 own IDs and relations', () => {
  const records = Array.from({ length: 20 }, (_, index) => adaptNativeTopologyRecord({
    body_id: 'BODY_A', coedge_id: `COEDGE_${index + 1}`, wire_id: 'WIRE_A',
    owning_face_id: 'FACE_A', edge_cell_id: `EDGE_${index + 1}`, coedge_index: index + 1
  }, 'coedge'));
  const model = buildTopologyItems([{ category: 'coedge', source: 'caa_native', records }], 'rev-1');
  assert.equal(model.items.length, 20);
  assert.equal(new Set(model.items.map(item => item.key)).size, 20);
  assert.equal(model.items[19].entityId, 'COEDGE_20');
  assert.equal(model.items[19].owningBodyId, 'BODY_A');
  assert.equal(model.items[19].underlyingEdgeId, 'EDGE_20');
  assert.equal(model.items[19].title, '有向边 020');
  assert.equal(filterTopologyItems(model.items, 'coedge', 'COEDGE_20')[0].title, '有向边 020');
  assert.ok(!sameTopologySelection(model.items[0], { id: 'BODY_A', kind: 'coedge', namespace: 'caa_native' }));
});

test('all six categories keep records beyond old 160 item cutoff', () => {
  const categories: TopologyCategory[] = ['body_solid', 'face', 'loop', 'coedge', 'edge', 'vertex'];
  const fields = ['body_id', 'cell_id', 'wire_id', 'coedge_id', 'cell_id', 'cell_id'];
  const inputs: TopologyInput[] = categories.map((category, categoryIndex) => ({
    category, source: 'caa_native',
    records: Array.from({ length: 180 }, (_, index) => ({
      [fields[categoryIndex]]: `${category}_${index + 1}`,
      ...(category === 'body_solid' ? { kind: 'body' } : {}),
      ...(category === 'face' ? { cell_kind: 'face' } : {}),
      ...(category === 'edge' ? { cell_kind: 'edge' } : {}),
      ...(category === 'vertex' ? { cell_kind: 'vertex' } : {})
    }))
  }));
  const model = buildTopologyItems(inputs, 'rev-1');
  for (const category of categories) assert.equal(filterTopologyItems(model.items, category, '').length, 180);
});

test('same text ID in native and STEP namespaces never cross-selects', () => {
  const model = buildTopologyItems([
    { category: 'face', source: 'caa_native', records: [{ cell_id: 'FACE_1' }] },
    { category: 'face', source: 'step_render', records: [{ entity_id: 'FACE_1' }] }
  ], 'rev-1', new Set(['FACE_1']));
  assert.equal(model.items.length, 2);
  assert.notEqual(model.items[0].key, model.items[1].key);
  assert.ok(!sameTopologySelection(model.items[0], { id: 'FACE_1', kind: 'face', namespace: 'step_render' }));
  assert.equal(model.items[0].canLocate, false);
  assert.equal(model.items[1].canLocate, true);
});

test('missing own ID is rejected; contradictory duplicate identities are diagnosed', () => {
  const model = buildTopologyItems([{ category: 'coedge', source: 'caa_native', records: [
    { body_id: 'BODY_A', wire_id: 'W1' },
    { coedge_id: 'C1', body_id: 'BODY_A', wire_id: 'W1' },
    { coedge_id: 'C1', body_id: 'BODY_A', wire_id: 'W2' }
  ] }], 'rev-1');
  assert.equal(model.items.length, 0);
  assert.equal(model.diagnostics.length, 2);
});

test('real native body record without kind uses body_id as its own identity', () => {
  const body = adaptNativeTopologyRecord({ body_id: 'TB000001', source_feature_id: 'F1', face_count: 24 }, 'body');
  const model = buildTopologyItems([{ category: 'body_solid', source: 'caa_native', records: [body] }], 'rev-1');
  assert.equal(model.items[0].kind, 'body');
  assert.equal(model.items[0].entityId, 'TB000001');
});

test('topology summaries show Chinese geometry types while raw codes remain searchable', () => {
  const model = buildTopologyItems([{ category: 'face', source: 'step_render', records: [
    { entity_id: 'F-CYL', geometry_type: 'cylinder', area: 1294.15 },
    { entity_id: 'F-TOR', geometry_type: 'torus', area: 140.635 },
    { entity_id: 'F-UNKNOWN', geometry_type: 'vendor_surface' }
  ] }], 'rev-1');
  assert.match(model.items[0].subtitle, /^圆柱面 · 面积 1294.15 mm²$/);
  assert.match(model.items[1].subtitle, /^圆环面 · 面积 140.635 mm²$/);
  assert.equal(model.items[2].subtitle, 'vendor_surface');
  assert.equal(filterTopologyItems(model.items, 'face', 'torus')[0].entityId, 'F-TOR');
  assert.equal(model.items[1].raw.geometry_type, 'torus');
});

test('missing persisted CATPart face channel retains mapped STEP faces for exact highlighting', () => {
  const mappedFaces = [{ entity_id: 'FACE_RENDER_1', face_id: 'FACE_RENDER_1',
    topology_source: 'step_render', geometry_type: 'cylinder' }];
  const faces = preferMappedTopologyFaces(mappedFaces, []);
  const item = buildTopologyItems([{ category: 'face', source: 'step_render', records: faces }],
    'rev-1', new Set(['FACE_RENDER_1'])).items[0];
  assert.equal(item.source, 'step_render');
  assert.equal(item.canLocate, true);
  const selection = resolveViewerSelection({ kind: 'face', id: item.entityId, namespace: item.source }, {
    selectionIndex: { schema_version: 'cad_viewer_selection_v1',
      render_face_to_primitives: { FACE_RENDER_1: ['PRIM_1'] } }
  });
  assert.equal(selection.context.mappingStatus, 'exact');
  assert.deepEqual(selection.context.primitiveIds, ['PRIM_1']);
});

test('mapped STEP Toroid surface keeps a readable face summary', () => {
  const model = buildTopologyItems([{ category: 'face', source: 'step_render', records: [{
    entity_id: 'FACE_TOROID', geometry_type: 'other', geometry: { surface_type_raw: 'Toroid' }
  }] }], 'rev-1', new Set(['FACE_TOROID']));
  assert.equal(model.items[0].subtitle, '圆环面');
});
