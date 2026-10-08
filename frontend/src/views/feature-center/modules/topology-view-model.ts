import type { SelectionTargetKind, TopologySelectionRecord } from './viewer-selection';
import { topologyGeometryLabel } from './topology-geometry-labels';

export type TopologyCategory = 'body_solid' | 'face' | 'loop' | 'coedge' | 'edge' | 'vertex';
export type TopologySource = 'caa_native' | 'step_render';
export type TopologyKind = Extract<SelectionTargetKind, 'body' | 'solid' | 'face' | 'loop' | 'coedge' | 'edge' | 'vertex'>;

export interface TopologyExplorerItem {
  key: string;
  entityId: string;
  source: TopologySource;
  kind: TopologyKind;
  category: TopologyCategory;
  title: string;
  subtitle: string;
  searchText: string;
  raw: Record<string, unknown>;
  owningBodyId: string;
  owningFaceId: string;
  wireId: string;
  underlyingEdgeId: string;
  canLocate: boolean;
}

export interface TopologyInput {
  category: TopologyCategory;
  source: TopologySource;
  records: Array<TopologySelectionRecord | Record<string, unknown>>;
}

export const topologyCategories: Array<{ value: TopologyCategory; label: string; icon: string }> = [
  { value: 'body_solid', label: '几何体/实体', icon: 'lucide:boxes' },
  { value: 'face', label: '面', icon: 'lucide:layers' },
  { value: 'loop', label: '边界环/线框', icon: 'lucide:scan' },
  { value: 'coedge', label: '有向边', icon: 'lucide:workflow' },
  { value: 'edge', label: '边', icon: 'lucide:move-diagonal' },
  { value: 'vertex', label: '顶点', icon: 'lucide:circle-dot' }
];

const kindNames: Record<TopologyKind, string> = {
  body: '几何体', solid: '实体', face: '面', loop: '边界环',
  coedge: '有向边', edge: '边', vertex: '顶点'
};

function stringField(raw: Record<string, unknown>, key: string): string {
  const value = raw[key];
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

/** Persisted face pages are optional for CATPart; the SelectionIndex faces remain usable. */
export function preferMappedTopologyFaces<T>(mappedFaces: T[], persistedFaces: T[]): T[] {
  return persistedFaces.length ? persistedFaces : mappedFaces;
}

function faceGeometryType(raw: Record<string, unknown>): string {
  const type = stringField(raw, 'surface_type') || stringField(raw, 'geometry_type') ||
    stringField(raw, 'kernel_surface_type');
  if (type && type !== 'other') return type;
  const geometry = raw.geometry;
  const kernelClass = geometry && typeof geometry === 'object' ?
    stringField(geometry as Record<string, unknown>, 'surface_type_raw') : '';
  return kernelClass || type;
}

export function ownId(raw: Record<string, unknown>, kind: TopologyKind, source: TopologySource): string {
  if (source === 'step_render') return stringField(raw, 'entity_id') || stringField(raw, 'id') || stringField(raw, 'face_id');
  if (kind === 'body') return stringField(raw, 'body_id');
  if (kind === 'loop') return stringField(raw, 'wire_id');
  if (kind === 'coedge') return stringField(raw, 'coedge_id');
  if (kind === 'face') return stringField(raw, 'cell_id') || stringField(raw, 'topology_id') || stringField(raw, 'face_id');
  return stringField(raw, 'cell_id') || stringField(raw, 'topology_id');
}

export type SourcedTopologyRecord = TopologySelectionRecord & { topology_source: TopologySource };

export function adaptNativeTopologyRecord(raw: Record<string, unknown>, kind: TopologyKind): SourcedTopologyRecord {
  const normalizedRaw = { ...raw, kind: stringField(raw, 'kind') || kind };
  return {
    id: ownId(raw, kind, 'caa_native'),
    parent_id: stringField(raw, 'parent_id') || stringField(raw, 'parent_entity_id'),
    owning_body_id: stringField(raw, 'owning_body_id') || stringField(raw, 'body_id'),
    topology_source: 'caa_native', raw: normalizedRaw
  };
}

export function adaptSelectionIndexRecord(record: TopologySelectionRecord): SourcedTopologyRecord {
  const raw = record.raw || (record as unknown as Record<string, unknown>);
  return { ...record, id: record.id, topology_source: 'step_render', raw };
}

export function topologyRecordKind(record: TopologySelectionRecord): string {
  const raw = record.raw || (record as unknown as Record<string, unknown>);
  return (stringField(raw, 'cell_kind') || stringField(raw, 'kind') || stringField(raw, 'topology_type')).toLowerCase();
}

function actualKind(raw: Record<string, unknown>, category: TopologyCategory): TopologyKind {
  if (category !== 'body_solid') return category === 'loop' ? 'loop' : category;
  const value = (stringField(raw, 'cell_kind') || stringField(raw, 'kind') ||
    stringField(raw, 'topology_type')).toLowerCase();
  return value === 'body' ? 'body' : 'solid';
}

function subtitle(raw: Record<string, unknown>, kind: TopologyKind, id: string): string {
  if (kind === 'coedge') {
    const edge = stringField(raw, 'edge_cell_id');
    const wire = stringField(raw, 'wire_id');
    return [edge && `关联边 ${edge}`, wire && `所属环 ${wire}`].filter(Boolean).join(' · ') || id;
  }
  if (kind === 'loop') return [
    stringField(raw, 'owning_face_id') && `所属面 ${stringField(raw, 'owning_face_id')}`,
    stringField(raw, 'closed_status') && `闭合 ${stringField(raw, 'closed_status')}`
  ].filter(Boolean).join(' · ') || id;
  if (kind === 'face') return [
    topologyGeometryLabel(faceGeometryType(raw)),
    (raw.area_mm2 ?? raw.area) != null && `面积 ${raw.area_mm2 ?? raw.area} mm²`
  ].filter(Boolean).join(' · ') || id;
  if (kind === 'edge') return [
    topologyGeometryLabel(stringField(raw, 'geometry_type') || stringField(raw, 'curve_type')),
    (raw.length_mm ?? raw.length) != null && `长度 ${raw.length_mm ?? raw.length} mm`
  ].filter(Boolean).join(' · ') || id;
  if (kind === 'vertex') {
    const point = raw.center_mm || raw.point_mm || raw.position_mm;
    return Array.isArray(point) ? point.slice(0, 3).join(', ') : id;
  }
  return stringField(raw, 'source_kind') || id;
}

/** The map key is a render identity. entityId remains the untouched API identity. */
export function buildTopologyItems(inputs: TopologyInput[], revisionId: string, renderFaceIds: ReadonlySet<string> = new Set()) {
  const items: TopologyExplorerItem[] = [];
  const diagnostics: string[] = [];
  const seen = new Map<string, string>();
  const conflicted = new Set<string>();
  const ordinalByKind = new Map<TopologyKind, number>();
  for (const input of inputs) for (const entry of input.records) {
    const wrapper = entry as TopologySelectionRecord;
    const raw = (wrapper.raw || entry) as Record<string, unknown>;
    const kind = actualKind(raw, input.category);
    const entityId = ownId(raw, kind, input.source);
    if (!entityId) {
      diagnostics.push(`${input.source}/${kind}: 缺少自身 ID，记录未纳入列表`);
      continue;
    }
    const key = JSON.stringify([revisionId, input.source, kind, entityId]);
    const owningBodyId = stringField(raw, 'owning_body_id') || stringField(raw, 'body_id');
    const owningFaceId = stringField(raw, 'owning_face_id');
    const wireId = stringField(raw, 'wire_id');
    const underlyingEdgeId = stringField(raw, 'edge_cell_id');
    const fingerprint = JSON.stringify([owningBodyId, owningFaceId, wireId, underlyingEdgeId, raw]);
    if (seen.has(key)) {
      if (seen.get(key) !== fingerprint) {
        conflicted.add(key);
        diagnostics.push(`${input.source}/${kind}/${entityId}: 同一身份存在冲突记录，已禁止选择`);
      }
      continue;
    }
    seen.set(key, fingerprint);
    const ordinal = (ordinalByKind.get(kind) || 0) + 1;
    ordinalByKind.set(kind, ordinal);
    const nativeOrdinal = raw.coedge_index ?? raw.wire_index ?? raw.topology_index;
    const name = stringField(raw, 'persistent_name') || stringField(raw, 'display_name') ||
      (kind === 'body' ? stringField(raw, 'name') : '');
    const title = name || `${kindNames[kind]} ${String(nativeOrdinal || ordinal).padStart(3, '0')}`;
    const secondary = subtitle(raw, kind, entityId);
    const rawGeometryType = kind === 'face' ? faceGeometryType(raw) :
      stringField(raw, 'geometry_type') || stringField(raw, 'curve_type');
    items.push({ key, entityId, source: input.source, kind, category: input.category,
      title, subtitle: secondary, searchText: `${title} ${secondary} ${entityId} ${kindNames[kind]} ${rawGeometryType}`.toLowerCase(),
      raw, owningBodyId, owningFaceId, wireId, underlyingEdgeId,
      canLocate: kind === 'face' && input.source === 'step_render' && renderFaceIds.has(entityId) });
  }
  return { items: items.filter(item => !conflicted.has(item.key)), diagnostics };
}

export function filterTopologyItems(items: TopologyExplorerItem[], category: TopologyCategory, keyword: string) {
  const query = keyword.trim().toLowerCase();
  return items.filter(item => item.category === category && (!query || item.searchText.includes(query)));
}

export function sameTopologySelection(item: TopologyExplorerItem, selected: {
  id: string; kind: string; namespace?: string
} | null) {
  return !!selected && item.entityId === selected.id && item.kind === selected.kind && item.source === selected.namespace;
}
