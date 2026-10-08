import type { CompositeField, CompositeStructureRecord } from '@/service/api/cad';

export const compositeTypes: Record<CompositeStructureRecord['kind'], { label: string; icon: string }> = {
  stacking: { label: '叠层', icon: 'mdi:layers-triple-outline' },
  group: { label: '铺层组', icon: 'mdi:folder-multiple-outline' },
  sequence: { label: '序列', icon: 'mdi:format-list-numbered' },
  ply: { label: '单层', icon: 'mdi:rhombus-outline' },
  cut_piece: { label: '子片', icon: 'mdi:vector-polyline' },
  cut_piece_group: { label: '子片组', icon: 'mdi:folder-multiple-outline' }
};

export function compositeType(kind: string) {
  return compositeTypes[kind as CompositeStructureRecord['kind']] || { label: '复材对象', icon: 'mdi:information-outline' };
}

export function compositeDetailKind(record: CompositeStructureRecord): 'stacking' | 'group' | 'sequence' | 'ply' | 'other' {
  return ['stacking', 'group', 'sequence', 'ply'].includes(record.kind) ? record.kind as 'stacking' | 'group' | 'sequence' | 'ply' : 'other';
}

export function compositeIdentityKey(revisionId: string, record: CompositeStructureRecord): string {
  return `${revisionId}:${record.document_id}:${record.kind}:${record.object_id}`;
}

export function orderStatus(status: string): string {
  if (status === 'native_complete') return '原生顺序已读取';
  if (status === 'partial') return '原生顺序部分可读';
  return '层序未取得';
}

export function updateStatus(status: string): { text: string; tone: 'success' | 'warning' | 'neutral' } {
  if (status === 'up_to_date') return { text: '原生对象已更新', tone: 'success' };
  if (status === 'not_up_to_date') return { text: '原生对象待更新', tone: 'warning' };
  return { text: '更新状态未知', tone: 'neutral' };
}

const unitLabels: Record<string, string> = {
  deg: '°', mm: 'mm', 'mm²': 'mm²', mm2: 'mm²', 'm²': 'm²', m2: 'm²',
  'm^-3*kg': 'kg/m³', 'kg/m³': 'kg/m³'
};

export function formatCompositeNumber(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (value === 0) return '0';
  const ordinary = new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 }).format(value);
  if (Number(ordinary.replaceAll(',', '')) !== 0) return ordinary;
  return value.toLocaleString('en-US', { maximumSignificantDigits: 6, maximumFractionDigits: 20, useGrouping: false });
}

export function formatCompositeField(field: CompositeField | undefined): { text: string; raw: string; status: string } {
  if (!field) return { text: '未采集', raw: '', status: 'unavailable' };
  const raw = `${String(field.raw_value ?? '')} ${field.raw_unit || ''}`.trim();
  if (field.read_status !== 'available') return {
    text: field.read_status === 'unsupported' ? '不支持读取' : '未读取', raw, status: field.read_status
  };
  const useNormalized = typeof field.normalized_value === 'number' && Number.isFinite(field.normalized_value);
  const unit = useNormalized ? field.normalized_unit : field.raw_unit;
  const rawValue = field.raw_value;
  let numeric: number | null = useNormalized ? field.normalized_value : null;
  if (numeric === null && typeof rawValue === 'number' && Number.isFinite(rawValue)) numeric = rawValue;
  if (numeric === null && typeof rawValue === 'string' && /^-?\d+(?:\.\d+)?$/.test(rawValue) &&
    rawValue.replace(/\D/g, '').length <= 15) numeric = Number(rawValue);
  const value = numeric === null ? (typeof rawValue === 'boolean' ? rawValue ? '是' : '否' :
    rawValue === null || rawValue === undefined || rawValue === '' ? '原生空值' : String(rawValue)) : formatCompositeNumber(numeric);
  const unitLabel = unitLabels[unit] || unit;
  return { text: unitLabel === '°' ? `${value}°` : `${value}${unitLabel ? ` ${unitLabel}` : ''}`, raw, status: field.read_status };
}

const fieldDefinitions: Record<string, { label: string; group: string }> = {
  composite_material_name: { label: '材料名称', group: 'material' },
  composite_material_type: { label: '材料类型', group: 'material' },
  composite_orientation: { label: '名义方向', group: 'material' },
  composite_cured_thickness: { label: '固化厚度', group: 'material' },
  composite_uncured_thickness: { label: '未固化厚度', group: 'material' },
  composite_density: { label: '材料密度', group: 'material' },
  composite_draping_direction: { label: '铺覆方向', group: 'material' },
  composite_area_m2: { label: '原生单层面积', group: 'geometry' },
  composite_reference_surface: { label: '参考曲面', group: 'geometry' },
  composite_reference_surface_object_id: { label: '参考曲面对象', group: 'geometry' }
};

export function compositeFieldRows(record: CompositeStructureRecord, group: string) {
  const groupKeys = ['composite_draping_direction', 'composite_reference_surface', 'composite_reference_surface_object_id'];
  return Object.entries(fieldDefinitions).filter(([key, definition]) =>
    (definition.group === group || group === 'group' && groupKeys.includes(key)) && key in record.fields)
    .map(([key, definition]) => {
      const field = record.fields[key];
      const formatted = formatCompositeField(field);
      if (field?.read_status === 'available' && key === 'composite_material_type' && field.raw_value === 'Uni-directional') {
        formatted.text = '单向材料';
      }
      if (field?.read_status === 'available' && key === 'composite_draping_direction') {
        if (field.raw_value === 'NEGATIVE') formatted.text = '反向';
        if (field.raw_value === 'POSITIVE') formatted.text = '正向';
      }
      return { key, label: definition.label, ...formatted, source: field?.source_api || '' };
    });
}

export function compositeTitle(record: CompositeStructureRecord): string {
  return `${compositeType(record.kind).label} · ${record.display_name || record.object_id}`;
}

export function compositeListItem(record: CompositeStructureRecord, revisionId: string) {
  const orientation = formatCompositeField(record.fields.composite_orientation);
  const summary = record.kind === 'ply' ?
    (orientation.status === 'available' ? orientation.text : '方向未读取') : orderStatus(record.order_status);
  const title = compositeTitle(record);
  return { key: compositeIdentityKey(revisionId, record), objectId: record.object_id, title,
    typeLabel: compositeType(record.kind).label, icon: compositeType(record.kind).icon,
    summary, orderText: orderStatus(record.order_status),
    searchText: `${title} ${record.object_id} ${record.kind} ${summary}`.toLowerCase() };
}

export interface CompositeMember {
  objectId: string;
  title: string;
  icon: string;
  index: number | null;
  unresolved: boolean;
  summary: string;
}

function member(id: string, records: CompositeStructureRecord[], index: number | null): CompositeMember {
  const row = records.find(item => item.object_id === id);
  return { objectId: id, title: row ? compositeTitle(row) : '名称待加载',
    icon: compositeType(row?.kind || '').icon, index, unresolved: !row,
    summary: row?.kind === 'ply' ? compositeListItem(row, '').summary : '' };
}

export function compositeMembers(record: CompositeStructureRecord, records: CompositeStructureRecord[]): CompositeMember[] {
  const listed = record.ordered_child_object_ids?.filter((id): id is string => Boolean(id)) || [];
  const ids = listed.length ? listed : records.filter(item => item.parent_object_ids.includes(record.object_id))
    .map(item => item.object_id);
  return ids.map((id, position) => member(id, records,
    listed.length && record.order_status === 'native_complete' ? position + 1 : null));
}

export function compositeParentLinks(record: CompositeStructureRecord, records: CompositeStructureRecord[]): CompositeMember[] {
  return record.parent_object_ids.map(id => member(id, records, null));
}
