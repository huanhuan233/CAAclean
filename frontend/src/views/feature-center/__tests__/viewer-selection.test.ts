import assert from 'node:assert/strict';
import test from 'node:test';
import { clearViewerSelection, resolveViewerSelection } from '../modules/viewer-selection';
import * as viewerSelection from '../modules/viewer-selection';

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

test('canvas hit without Face or BOM mesh map keeps the clicked render mesh as a highlight preview', () => {
  const selection = resolveViewerSelection(
    { kind: 'part', id: 'PART-1', source: 'canvas', renderObjectUuid: 'MESH-UUID' },
    { bomNodes: [] }
  );

  assert.equal(selection.primary?.kind, 'part');
  assert.deepEqual(selection.context.renderObjectUuids, ['MESH-UUID']);
  assert.equal(selection.context.mappingStatus, 'candidate');
  assert.equal(selection.context.mappingAuthority, 'canvas_hit_preview');
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

test('face primary is not replaced by its associated features in the detail projection', () => {
  assert.equal(typeof viewerSelection.projectSelectionIds, 'function');
  const selection = resolveViewerSelection({ kind: 'face', id: 'FACE-1' }, { selectionIndex, faceMeshMap, featureMeshMap });
  assert.deepEqual(viewerSelection.projectSelectionIds(selection), {
    faceId: 'FACE-1', nativeFeatureId: '', recognizedFeatureId: ''
  });
});

test('candidate native face identity never becomes a render primitive selection', () => {
  const selection = resolveViewerSelection({ kind: 'native_feature', id: 'object_7' }, {
    selectionIndex: { ...selectionIndex, native_feature_to_native_faces: { object_7: ['NATIVE-FACE-1'] } },
    faceMeshMap,
    featureMeshMap
  });
  assert.deepEqual(selection.context.nativeFaceIds, ['NATIVE-FACE-1']);
  assert.deepEqual(selection.context.primitiveIds, []);
  assert.notEqual(selection.context.mappingStatus, 'exact');
  assert.notEqual(selection.context.mappingStatus, 'runtime_current_revision');
});

test('verified canonical Hole can highlight only when selection and mesh share shape hash', () => {
  const canonical = [{
    feature_center_id: 'FC-A', family: 'hole', subtype: 'simple', review_state: 'auto_verified',
    geometry_refs: { face_ids: ['FACE-1'] }, native_feature_ids: ['object_7'],
    typed_payload: { geometry_verification: { status: 'verified' } }, provenance: {}
  }];
  const trusted = resolveViewerSelection({ kind: 'native_feature', id: 'object_7' }, {
    selectionIndex: { ...selectionIndex, shape_hash: 'shape' }, faceMeshMap, featureMeshMap,
    canonicalFeatures: canonical
  });
  assert.equal(trusted.context.mappingStatus, 'exact');
  assert.deepEqual(trusted.context.primitiveIds, ['PRIM-1']);

  const mismatched = resolveViewerSelection({ kind: 'native_feature', id: 'object_7' }, {
    selectionIndex: { ...selectionIndex, shape_hash: 'different-shape' }, faceMeshMap, featureMeshMap,
    canonicalFeatures: canonical
  });
  assert.equal(mismatched.context.mappingStatus, 'candidate');
  assert.deepEqual(mismatched.context.primitiveIds, []);
});

test('tree occurrence remains primary while canonical link resolves definition object id', () => {
  const selection = resolveViewerSelection({ kind: 'native_feature', id: 'occurrence_7' }, {
    selectionIndex: { ...selectionIndex, shape_hash: 'shape' }, faceMeshMap, featureMeshMap,
    nativeFeatures: [{ feature_id: 'occurrence_7', attributes: { object_id: 'object_7' } }],
    canonicalFeatures: [{
      feature_center_id: 'FC-A', family: 'hole', subtype: 'simple', review_state: 'auto_verified',
      geometry_refs: { face_ids: ['FACE-1'] }, native_feature_ids: ['object_7'],
      typed_payload: { geometry_verification: { status: 'verified' } }, provenance: {}
    }]
  });
  assert.equal(selection.primary?.id, 'occurrence_7');
  assert.deepEqual(selection.context.nativeFeatureIds, ['object_7']);
  assert.equal(selection.context.mappingStatus, 'exact');
  assert.deepEqual(selection.context.primitiveIds, ['PRIM-1']);
});

test('unverified native feature uses same-shape candidate highlight with explicit risk', () => {
  const selection = resolveViewerSelection({ kind: 'native_feature', id: 'O1' }, {
    selectionIndex: { ...selectionIndex, shape_hash: 'shape' }, faceMeshMap, featureMeshMap,
    canonicalFeatures: [{
      feature_center_id: 'FC-A', family: 'hole', subtype: 'simple', review_state: 'needs_review',
      geometry_refs: { face_ids: ['FACE-1'] }, native_feature_ids: ['O1'],
      typed_payload: { geometry_verification: { status: 'needs_review' } }, provenance: {}
    }]
  });
  assert.equal(selection.context.mappingStatus, 'candidate');
  assert.deepEqual(selection.context.primitiveIds, ['PRIM-1']);
  assert.match(selection.context.diagnostics.join(';'), /CANDIDATE_HIGHLIGHT_RISK/);
});

test('single CATPart without a feature crosswalk previews whole part but never calls it exact', () => {
  const selection = resolveViewerSelection({ kind: 'native_feature', id: 'O1' }, {
    faceMeshMap,
    bomNodes: [{ node_id: 'PART', node_type: 'part', children: [] } as never]
  });
  assert.equal(selection.context.mappingStatus, 'candidate');
  assert.deepEqual(selection.context.primitiveIds, ['PRIM-1']);
  assert.equal(selection.context.mappingAuthority, 'whole_part_preview');
  assert.match(selection.context.diagnostics.join(';'), /WHOLE_PART_PREVIEW/);
});
