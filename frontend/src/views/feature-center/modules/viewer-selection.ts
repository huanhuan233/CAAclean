import type { CanonicalFeatureRecord, FeatureMeshMap } from './feature-center-bundle';
import type { NativeFeatureRecord } from './native-feature-tree';

export type SelectionTargetKind =
  | 'assembly'
  | 'part_instance'
  | 'part'
  | 'body'
  | 'solid'
  | 'native_feature'
  | 'mbd_annotation'
  | 'mbd_set'
  | 'mbd_view'
  | 'mbd_capture'
  | 'recognized_feature'
  | 'face'
  | 'loop'
  | 'coedge'
  | 'edge'
  | 'vertex';

export type SelectionMappingStatus = 'exact' | 'runtime_current_revision' | 'candidate' | 'ambiguous' | 'unavailable';

export interface SelectionTarget {
  kind: SelectionTargetKind;
  id: string;
  namespace?: 'caa_native' | 'step_render';
  label?: string;
  instancePath?: string;
  renderObjectUuid?: string;
  source?: 'canvas' | 'bom' | 'native_feature' | 'recognized_feature' | 'topology' | 'detail' | 'mbd';
  raw?: unknown;
}

export interface SelectionContext {
  primitiveIds: string[];
  renderObjectUuids: string[];
  renderFaceIds: string[];
  nativeFaceIds: string[];
  bomNodeIds: string[];
  instanceIds: string[];
  partIds: string[];
  bodyIds: string[];
  solidIds: string[];
  nativeFeatureIds: string[];
  recognizedFeatureIds: string[];
  loopIds: string[];
  coedgeIds: string[];
  edgeIds: string[];
  vertexIds: string[];
  mappingStatus: SelectionMappingStatus;
  mappingAuthority?: string;
  confidence?: number;
  diagnostics: string[];
}

export interface ViewerSelection {
  primary: SelectionTarget | null;
  context: SelectionContext;
}

export interface ViewerSelectionIndex {
  schema_version: 'cad_viewer_selection_v1' | string;
  shape_hash?: string;
  mapping_summary?: Record<string, number>;
  primitive_to_render_face?: Record<string, string>;
  render_face_to_primitives?: Record<string, string[]>;
  render_face_to_recognized_features?: Record<string, string[]>;
  recognized_feature_to_render_faces?: Record<string, string[]>;
  recognized_feature_to_primitives?: Record<string, string[]>;
  native_feature_to_native_faces?: Record<string, string[]>;
  native_face_to_body?: Record<string, string>;
  topology?: TopologySelectionIndex;
  bom_node_to_descendant_primitives?: Record<string, string[]>;
}

export interface TopologySelectionIndex {
  bodies?: Record<string, TopologySelectionRecord>;
  solids?: Record<string, TopologySelectionRecord>;
  faces?: Record<string, TopologySelectionRecord>;
  loops?: Record<string, TopologySelectionRecord>;
  wires?: Record<string, TopologySelectionRecord>;
  coedges?: Record<string, TopologySelectionRecord>;
  edges?: Record<string, TopologySelectionRecord>;
  vertices?: Record<string, TopologySelectionRecord>;
}

export interface TopologySelectionRecord {
  id: string;
  parent_id?: string;
  owning_body_id?: string;
  relations?: Array<{ relation_type?: string; source_id?: string; target_id?: string }>;
  raw?: Record<string, unknown>;
}

export interface SelectionResources {
  selectionIndex?: ViewerSelectionIndex | null;
  faceMeshMap?: {
    faces?: Record<string, { mesh_primitive_id?: string }>;
    primitive_to_face?: Record<string, string>;
  } | null;
  featureMeshMap?: FeatureMeshMap | null;
  bomNodes?: Api.ComponentBuild.ViewerBomNode[];
  canonicalFeatures?: CanonicalFeatureRecord[];
  nativeFeatures?: NativeFeatureRecord[];
}

export function emptySelectionContext(): SelectionContext {
  return {
    primitiveIds: [],
    renderObjectUuids: [],
    renderFaceIds: [],
    nativeFaceIds: [],
    bomNodeIds: [],
    instanceIds: [],
    partIds: [],
    bodyIds: [],
    solidIds: [],
    nativeFeatureIds: [],
    recognizedFeatureIds: [],
    loopIds: [],
    coedgeIds: [],
    edgeIds: [],
    vertexIds: [],
    mappingStatus: 'unavailable',
    diagnostics: []
  };
}

export function clearViewerSelection(): ViewerSelection {
  return { primary: null, context: emptySelectionContext() };
}

export function resolveViewerSelection(target: SelectionTarget, resources: SelectionResources): ViewerSelection {
  const context = emptySelectionContext();
  const diagnostics: string[] = [];
  const index = resources.selectionIndex;
  const topology = index?.topology;
  if (target.source === 'canvas') push(context.renderObjectUuids, target.renderObjectUuid);

  if (target.kind === 'assembly' || target.kind === 'part_instance' || target.kind === 'part') {
    const node = findBomNode(resources.bomNodes || [], target.id);
    if (node) {
      push(context.bomNodeIds, node.node_id);
      push(context.instanceIds, node.instance_name);
      push(context.partIds, node.part_number || node.node_id);
      pushMany(context.primitiveIds, node.descendant_mesh_primitive_ids || node.mesh_primitive_ids);
      context.mappingStatus = context.primitiveIds.length ? 'exact' : 'unavailable';
      context.mappingAuthority = context.primitiveIds.length ? 'viewer_bom_descendant_primitives' : undefined;
      if (!context.primitiveIds.length) diagnostics.push('BOM_PRIMITIVES_UNAVAILABLE');
    } else {
      diagnostics.push('BOM_NODE_NOT_FOUND');
    }
  }

  if (target.kind === 'recognized_feature') {
    push(context.recognizedFeatureIds, target.id);
    pushMany(context.renderFaceIds, index?.recognized_feature_to_render_faces?.[target.id]);
    pushMany(context.primitiveIds, index?.recognized_feature_to_primitives?.[target.id]);
    const fallbackEntry = resources.featureMeshMap?.features[target.id];
    pushMany(context.renderFaceIds, fallbackEntry?.face_ids);
    pushMany(context.primitiveIds, fallbackEntry?.mesh_primitive_ids);
    context.mappingStatus = context.renderFaceIds.length || context.primitiveIds.length ? 'exact' : 'unavailable';
    context.mappingAuthority = context.mappingStatus === 'exact' ? 'feature_mesh_map' : undefined;
    if (context.mappingStatus === 'unavailable') diagnostics.push('RECOGNIZED_FEATURE_MESH_MAP_MISSING');
  }

  if (target.kind === 'native_feature') {
    const treeRecord = (resources.nativeFeatures || []).find(feature => feature.feature_id === target.id);
    const objectId = typeof treeRecord?.attributes?.object_id === 'string' && treeRecord.attributes.object_id
      ? treeRecord.attributes.object_id : target.id;
    push(context.nativeFeatureIds, objectId);
    pushMany(context.nativeFaceIds, index?.native_feature_to_native_faces?.[objectId]);
    const linked = (resources.canonicalFeatures || []).filter(feature =>
      feature.native_feature_ids.includes(objectId)
    );
    pushMany(
      context.recognizedFeatureIds,
      linked.map(feature => feature.feature_center_id)
    );
    const sameShape = Boolean(index?.shape_hash && index.shape_hash === resources.featureMeshMap?.shape_hash);
    let verifiedRange = false;
    for (const feature of linked) {
      const verification = feature.typed_payload?.geometry_verification as Record<string, unknown> | undefined;
      const entry = resources.featureMeshMap?.features[feature.feature_center_id];
      const verified = sameShape && feature.review_state === 'auto_verified' && verification?.status === 'verified';
      const sameFaces = Boolean(entry && feature.geometry_refs.face_ids.length > 0 &&
        feature.geometry_refs.face_ids.every(faceId => entry.face_ids.includes(faceId)));
      const mapped = Boolean(entry && entry.mesh_primitive_ids.length > 0 &&
        entry.mesh_primitive_ids.every(primitiveId => index?.primitive_to_render_face?.[primitiveId]));
      if (sameShape && sameFaces && mapped) {
        pushMany(context.renderFaceIds, feature.geometry_refs.face_ids);
        pushMany(context.primitiveIds, entry?.mesh_primitive_ids);
        verifiedRange ||= verified;
      }
    }
    const productOccurrenceId = treeRecord?.attributes?.product_occurrence_id;
    const singlePart = resources.bomNodes?.length === 1 &&
      resources.bomNodes[0].node_type === 'part' && !(resources.bomNodes[0].children || []).length;
    if (!context.primitiveIds.length && singlePart && !productOccurrenceId) {
      pushMany(context.primitiveIds, Object.keys(resources.faceMeshMap?.primitive_to_face || {}));
      if (context.primitiveIds.length) diagnostics.push('FEATURE_RANGE_UNLOCATED_WHOLE_PART_PREVIEW');
    }
    context.mappingStatus = context.primitiveIds.length && verifiedRange ? 'exact' :
      context.primitiveIds.length || context.nativeFaceIds.length || linked.length ? 'candidate' : 'unavailable';
    context.mappingAuthority = context.mappingStatus === 'exact' ? 'verified_canonical_same_shape_mesh_map' :
      context.primitiveIds.length && !context.renderFaceIds.length ? 'whole_part_preview' :
      context.primitiveIds.length ? 'same_shape_canonical_candidate_preview' :
      context.nativeFaceIds.length ? 'native_feature_final_face_candidate' :
        linked.length ? 'canonical_feature_association' : undefined;
    if (context.mappingStatus === 'candidate' && context.primitiveIds.length)
      diagnostics.push('CANDIDATE_HIGHLIGHT_RISK');
    if (context.mappingStatus !== 'exact') diagnostics.push('NATIVE_FEATURE_RENDER_MAPPING_NOT_VERIFIED');
  }

  if (target.kind === 'face' && target.namespace !== 'caa_native') {
    push(context.renderFaceIds, target.id);
    pushMany(context.primitiveIds, index?.render_face_to_primitives?.[target.id]);
    push(context.primitiveIds, resources.faceMeshMap?.faces?.[target.id]?.mesh_primitive_id);
    const featureIds =
      index?.render_face_to_recognized_features?.[target.id] ||
      reverseFeaturesForFace(resources.featureMeshMap, target.id);
    pushMany(context.recognizedFeatureIds, featureIds);
    context.mappingStatus = context.primitiveIds.length ? 'exact' : 'unavailable';
    context.mappingAuthority = context.primitiveIds.length ? 'render_face_mesh_map' : undefined;
    if ((featureIds || []).length > 1) diagnostics.push('FACE_HAS_MULTIPLE_RECOGNIZED_FEATURES');
  }

  if (target.kind === 'body') {
    push(context.bodyIds, target.id);
    pushMany(context.renderFaceIds, descendantTopologyIds(topology, target.id, 'faces'));
    collectPrimitivesForFaces(context, resources);
  }
  if (target.kind === 'solid') {
    push(context.solidIds, target.id);
    pushMany(context.renderFaceIds, descendantTopologyIds(topology, target.id, 'faces'));
    collectPrimitivesForFaces(context, resources);
  }
  if (target.kind === 'loop') {
    push(context.loopIds, target.id);
    pushMany(context.renderFaceIds, adjacentTopologyIds(topology?.loops?.[target.id], 'face'));
    pushMany(context.edgeIds, adjacentTopologyIds(topology?.loops?.[target.id], 'edge'));
    collectPrimitivesForFaces(context, resources);
  }
  if (target.kind === 'coedge') {
    push(context.coedgeIds, target.id);
    pushMany(context.renderFaceIds, adjacentTopologyIds(topology?.coedges?.[target.id], 'face'));
    pushMany(context.edgeIds, adjacentTopologyIds(topology?.coedges?.[target.id], 'edge'));
    collectPrimitivesForFaces(context, resources);
  }
  if (target.kind === 'edge') {
    push(context.edgeIds, target.id);
    pushMany(context.renderFaceIds, adjacentTopologyIds(topology?.edges?.[target.id], 'face'));
    collectPrimitivesForFaces(context, resources);
    diagnostics.push('EDGE_OVERLAY_GEOMETRY_UNAVAILABLE');
  }
  if (target.kind === 'vertex') {
    push(context.vertexIds, target.id);
    pushMany(context.renderFaceIds, adjacentTopologyIds(topology?.vertices?.[target.id], 'face'));
    collectPrimitivesForFaces(context, resources);
    diagnostics.push('VERTEX_OVERLAY_GEOMETRY_UNAVAILABLE');
  }

  // Shared or adjacent faces describe relationships, not a precise render range for a
  // native boundary object. Keep those IDs for detail links but never paint a whole face.
  if (target.namespace === 'caa_native' || ['loop', 'coedge', 'edge', 'vertex'].includes(target.kind)) {
    context.primitiveIds = [];
    context.mappingStatus = 'unavailable';
    context.mappingAuthority = undefined;
    diagnostics.push('TOPOLOGY_LOCAL_RENDER_RANGE_UNAVAILABLE');
  }

  if (target.kind !== 'native_feature' && context.mappingStatus === 'unavailable' && context.primitiveIds.length) {
    context.mappingStatus = 'exact';
    context.mappingAuthority = context.mappingAuthority || 'selection_index';
  }
  if (target.source === 'canvas' && context.mappingStatus === 'unavailable' && context.renderObjectUuids.length) {
    const singlePart = (target.kind === 'part' || target.kind === 'part_instance') &&
      resources.bomNodes?.length === 1 && resources.bomNodes[0].node_id === target.id &&
      resources.bomNodes[0].node_type === 'part' && !(resources.bomNodes[0].children || []).length;
    context.mappingStatus = 'candidate';
    context.mappingAuthority = singlePart ? 'whole_part_preview' : 'canvas_hit_preview';
    diagnostics.push(singlePart ? 'WHOLE_PART_PREVIEW_ONLY' : 'CANVAS_HIT_PREVIEW_ONLY');
  }
  context.diagnostics = uniqueStrings([...context.diagnostics, ...diagnostics]);
  normalizeContext(context);
  return { primary: target, context };
}

export function selectionPrimaryId(selection: ViewerSelection, kind: SelectionTargetKind) {
  return selection.primary?.kind === kind ? selection.primary.id : '';
}

export function projectSelectionIds(selection: ViewerSelection) {
  const primary = selection.primary;
  return {
    faceId: primary?.kind === 'face' ? primary.id : '',
    nativeFeatureId: primary?.kind === 'native_feature' ? primary.id : '',
    recognizedFeatureId: primary?.kind === 'recognized_feature' ? primary.id : ''
  };
}

function collectPrimitivesForFaces(context: SelectionContext, resources: SelectionResources) {
  for (const faceId of context.renderFaceIds) {
    pushMany(context.primitiveIds, resources.selectionIndex?.render_face_to_primitives?.[faceId]);
    push(context.primitiveIds, resources.faceMeshMap?.faces?.[faceId]?.mesh_primitive_id);
  }
}

function reverseFeaturesForFace(mapping: FeatureMeshMap | null | undefined, faceId: string) {
  const featureIds: string[] = [];
  for (const [featureId, entry] of Object.entries(mapping?.features || {})) {
    if (entry.face_ids.includes(faceId)) featureIds.push(featureId);
  }
  return featureIds.sort();
}

function descendantTopologyIds(
  topology: TopologySelectionIndex | undefined,
  rootId: string,
  group: keyof TopologySelectionIndex
) {
  const ids: string[] = [];
  const entries = topology?.[group] || {};
  for (const [id, record] of Object.entries(entries)) {
    const parent = record.parent_id || record.owning_body_id || '';
    if (parent === rootId) ids.push(id);
  }
  return ids;
}

function adjacentTopologyIds(record: TopologySelectionRecord | undefined, expected: string) {
  if (!record) return [];
  const ids: string[] = [];
  for (const relation of record.relations || []) {
    const relationType = String(relation.relation_type || '').toLowerCase();
    if (!relationType.includes(expected)) continue;
    push(ids, relation.source_id);
    push(ids, relation.target_id);
  }
  return ids.filter(id => id !== record.id);
}

function findBomNode(nodes: Api.ComponentBuild.ViewerBomNode[], id: string): Api.ComponentBuild.ViewerBomNode | null {
  for (const node of nodes) {
    if (node.node_id === id) return node;
    const child = findBomNode(node.children, id);
    if (child) return child;
  }
  return null;
}

function push(values: string[], value: unknown) {
  if (typeof value === 'string' && value) values.push(value);
}

function pushMany(values: string[], additions: unknown) {
  if (!Array.isArray(additions)) return;
  additions.forEach(value => push(values, value));
}

function normalizeContext(context: SelectionContext) {
  context.primitiveIds = uniqueStrings(context.primitiveIds);
  context.renderObjectUuids = uniqueStrings(context.renderObjectUuids);
  context.renderFaceIds = uniqueStrings(context.renderFaceIds);
  context.nativeFaceIds = uniqueStrings(context.nativeFaceIds);
  context.bomNodeIds = uniqueStrings(context.bomNodeIds);
  context.instanceIds = uniqueStrings(context.instanceIds);
  context.partIds = uniqueStrings(context.partIds);
  context.bodyIds = uniqueStrings(context.bodyIds);
  context.solidIds = uniqueStrings(context.solidIds);
  context.nativeFeatureIds = uniqueStrings(context.nativeFeatureIds);
  context.recognizedFeatureIds = uniqueStrings(context.recognizedFeatureIds);
  context.loopIds = uniqueStrings(context.loopIds);
  context.coedgeIds = uniqueStrings(context.coedgeIds);
  context.edgeIds = uniqueStrings(context.edgeIds);
  context.vertexIds = uniqueStrings(context.vertexIds);
}

function uniqueStrings(values: string[]) {
  return [...new Set(values.filter(Boolean))].sort();
}
