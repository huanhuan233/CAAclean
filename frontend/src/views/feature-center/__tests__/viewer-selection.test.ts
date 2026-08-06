import assert from 'node:assert/strict';
import test from 'node:test';
import { clearViewerSelection, resolveViewerSelection } from '../modules/viewer-selection';

const faceMeshMap = {
  faces: {
    'FACE-1': { mesh_primitive_id: 'PRIM-1', primitive_index: 0 }
  },
  primitive_to_face: { 'PRIM-1': 'FACE-1' }
};

const featureMeshMap = {
  schema_version: 'feature_mesh_map_v1',
  shape_hash: 'shape',
  features: {
    'FC-A': { face_ids: ['FACE-1'], mesh_primitive_ids: ['PRIM-1'] },
    'FC-B': { face_ids: ['FACE-1'], mesh_primitive_ids: ['PRIM-1'] }
  }
};

const selectionIndex = {
  schema_version: 'cad_viewer_selection_v1',
  primitive_to_render_face: { 'PRIM-1': 'FACE-1' },
  render_face_to_primitives: { 'FACE-1': ['PRIM-1'] },
  render_face_to_recognized_features: { 'FACE-1': ['FC-A', 'FC-B'] },
  recognized_feature_to_render_faces: {
    'FC-A': ['FACE-1'],
    'FC-B': ['FACE-1']
  },
  recognized_feature_to_primitives: {
    'FC-A': ['PRIM-1'],
    'FC-B': ['PRIM-1']
  },
  native_feature_to_native_faces: {}
};

test('face selection keeps the face as primary and records all feature candidates', () => {
  const selection = resolveViewerSelection(
    { kind: 'face', id: 'FACE-1' },
    { selectionIndex, faceMeshMap, featureMeshMap }
  );

  assert.equal(selection.primary?.kind, 'face');
  assert.equal(selection.primary?.id, 'FACE-1');
  assert.deepEqual(selection.context.primitiveIds, ['PRIM-1']);
  assert.deepEqual(selection.context.recognizedFeatureIds, ['FC-A', 'FC-B']);
  assert.equal(selection.context.mappingStatus, 'exact');
  assert.match(selection.context.diagnostics.join(';'), /FACE_HAS_MULTIPLE_RECOGNIZED_FEATURES/);
});

test('recognized feature selection highlights mapped faces without guessing native history', () => {
  const selection = resolveViewerSelection(
    { kind: 'recognized_feature', id: 'FC-A' },
    { selectionIndex, faceMeshMap, featureMeshMap }
  );

  assert.equal(selection.primary?.kind, 'recognized_feature');
  assert.deepEqual(selection.context.renderFaceIds, ['FACE-1']);
  assert.deepEqual(selection.context.primitiveIds, ['PRIM-1']);
  assert.equal(selection.context.mappingAuthority, 'feature_mesh_map');
});

test('bom assembly selection uses descendant primitive ids from the contract', () => {
  const selection = resolveViewerSelection(
    { kind: 'assembly', id: 'ASM-1' },
    {
      bomNodes: [
        {
          node_id: 'ASM-1',
          parent_id: '',
          name: 'Assembly',
          part_number: 'ASM',
          instance_name: 'ASM.1',
          version: '',
          material: '',
          node_type: 'assembly',
          quantity: 1,
          source_format: 'CATPART',
          level: 0,
          transform: null,
          mesh_primitive_ids: [],
          descendant_mesh_primitive_ids: ['PRIM-1', 'PRIM-2'],
          entity_ids: [],
          solid_count: 0,
          volume: null,
          bounding_box: null,
          assembly_path: '/ASM.1',
          constraint_status: '',
          constraint_count: null,
          children: []
        }
      ]
    }
  );

  assert.equal(selection.primary?.kind, 'assembly');
  assert.deepEqual(selection.context.primitiveIds, ['PRIM-1', 'PRIM-2']);
  assert.equal(selection.context.mappingAuthority, 'viewer_bom_descendant_primitives');
});

test('missing stable mapping stays unavailable instead of falling back to names or colors', () => {
  const selection = resolveViewerSelection(
    { kind: 'face', id: 'FACE-MISSING', label: 'pretty blue face' },
    { selectionIndex, faceMeshMap, featureMeshMap }
  );

  assert.equal(selection.primary?.id, 'FACE-MISSING');
  assert.equal(selection.context.mappingStatus, 'unavailable');
  assert.deepEqual(selection.context.primitiveIds, []);
});

test('clear selection has no retained context', () => {
  const selection = clearViewerSelection();

  assert.equal(selection.primary, null);
  assert.deepEqual(selection.context.primitiveIds, []);
  assert.equal(selection.context.mappingStatus, 'unavailable');
});
