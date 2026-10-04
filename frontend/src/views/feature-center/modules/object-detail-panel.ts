import type { CanonicalFeatureRecord } from './feature-center-bundle';
import type { NativeFeatureRecord } from './native-feature-tree';
import type { SelectionContext, SelectionTarget } from './viewer-selection';

export type StatusTone = 'primary' | 'success' | 'warning' | 'danger' | 'info';

export interface DetailValue {
  text: string;
  fullText: string;
  empty: boolean;
  raw: unknown;
  statusTone?: StatusTone;
}

export interface DetailField {
  key: string;
  label: string;
  value: DetailValue;
}

export interface ParameterField extends DetailField {}

export interface GeometryLink {
  id: string;
  label: string;
  kind: string;
  clickable: boolean;
}

const EMPTY_TEXT = '—';

const COMMON_LABELS: Record<string, string> = {
  id: 'ID',
  feature_id: 'Feature ID',
  feature_center_id: 'Feature Center ID',
  display_name: '显示名称',
  internal_name: '内部名称',
  native_type: '原生类型',
  startup_type: 'StartUp',
  canonical_native_type: '标准原生类型',
  container_kind: '容器',
  parent_id: '父级 ID',
  tree_path: '树路径',
  traversal_index: '建模顺序',
  native_enumeration_index: '原生枚举序号',
  container_enumeration_index: '容器枚举序号',
  update_status: '更新状态',
  decoder_id: 'Decoder ID',
  decode_level: '解码层级',
  decode_status: '解码状态',
  decoder_status: 'Decoder 状态',
  payload_type: 'Payload 类型',
  payload_extraction_status: 'Payload 状态',
  family: '族',
  subtype: '子类型',
  review_state: '复核状态',
  native_feature_ids: '原生来源',
  geometry_refs: '几何引用',
  typed_payload: '类型化参数',
  provenance: '证据来源',
  face_id: 'Face ID',
  surface_type: '曲面类型',
  kernel_surface_type: 'Kernel 曲面类型',
  area: '面积',
  centroid: '质心',
  bounding_box: '包围盒',
  adjacent_face_ids: '相邻面',
  boundary_edge_ids: '边界边',
  topology_fingerprint: '拓扑指纹',
  node_id: '节点 ID',
  name: '名称',
  part_number: '零件号',
  instance_name: '实例名称',
  version: '版本',
  material: '材料',
  node_type: '节点类型',
  quantity: '数量',
  source_format: '来源格式',
  level: '层级',
  assembly_path: '装配路径',
  solid_count: 'Solid 数',
  volume: '体积',
  mappingStatus: '映射状态',
  mappingAuthority: 'Authority',
  confidence: '置信度',
  primitiveIds: 'Primitive',
  renderFaceIds: 'Render Face',
  nativeFaceIds: '原生 Face',
  bomNodeIds: 'BOM 节点',
  instanceIds: '实例',
  partIds: '零件',
  bodyIds: 'Body',
  solidIds: 'Solid',
  nativeFeatureIds: '原生特征',
  recognizedFeatureIds: '识别特征',
  loopIds: 'Loop',
  coedgeIds: 'Coedge',
  edgeIds: 'Edge',
  vertexIds: 'Vertex',
  diagnostics: '诊断'
};

const STATUS_LABELS: Record<string, string> = {
  success: '成功',
  succeeded: '成功',
  completed: '完成',
  complete: '已完成',
  measured: '已测量',
  ready: '就绪',
  active: '有效',
  up_to_date: '最新',
  runtime_current_revision: '当前版本',
  exact: '精确映射',
  failed: '失败',
  error: '错误',
  rejected: '已拒绝',
  unsupported: '不支持',
  ambiguous: '有歧义',
  warning: '警告',
  candidate: '候选',
  pending: '等待',
  processing: '处理中',
  unavailable: '不可用',
  disabled: '禁用',
  not_applicable: '不适用',
  not_evaluated: '未判定',
  budget_exceeded: '预算不足，部分未计算',
  complete_no_relation: '已计算，未发现适用关系',
  no_eligible_candidates: '无适用候选',
  calculation_failed: '计算失败',
  proxy_overlap_unverified: '代理范围重叠，实体关系未核验',
  overlap_or_contact: '旧版：重叠或接触未区分'
};

const STATUS_TONES: Record<string, StatusTone> = {
  success: 'success',
  succeeded: 'success',
  completed: 'success',
  ready: 'success',
  active: 'success',
  up_to_date: 'success',
  runtime_current_revision: 'success',
  exact: 'success',
  failed: 'danger',
  error: 'danger',
  rejected: 'danger',
  unsupported: 'warning',
  ambiguous: 'warning',
  warning: 'warning',
  candidate: 'warning',
  pending: 'info',
  processing: 'primary',
  unavailable: 'info',
  disabled: 'info',
  not_applicable: 'info'
};

const STATUS_KEYS = new Set([
  'status',
  'update_status',
  'decoder_status',
  'decode_status',
  'payload_extraction_status',
  'review_state',
  'mappingStatus',
  'load_status',
  'read_status',
  'value_source',
  'transform_status'
]);

const NATIVE_FEATURE_ORDER = [
  'feature_id',
  'display_name',
  'native_type',
  'startup_type',
  'canonical_native_type',
  'container_kind',
  'parent_id',
  'tree_path',
  'traversal_index',
  'update_status',
  'decoder_id',
  'decoder_status',
  'decode_status',
  'payload_extraction_status',
  'decode_level',
  'payload_type'
];

const RECOGNIZED_FEATURE_ORDER = [
  'feature_center_id',
  'family',
  'subtype',
  'review_state',
  'geometry_refs',
  'native_feature_ids',
  'provenance'
];

const FACE_ORDER = [
  'face_id',
  'surface_type',
  'kernel_surface_type',
  'area',
  'centroid',
  'bounding_box',
  'adjacent_face_ids',
  'boundary_edge_ids',
  'topology_fingerprint'
];

const BOM_ORDER = [
  'node_id',
  'name',
  'part_number',
  'instance_name',
  'version',
  'material',
  'node_type',
  'quantity',
  'source_format',
  'level',
  'assembly_path',
  'solid_count',
  'volume'
];

const PARAMETER_CONTAINER_KEYS = new Set(['native_feature_parameters', 'native_hole', 'native_prism', 'native_fillet', 'native_chamfer', 'native_sketch', 'attributes', 'parameter', 'typed_payload']);
const INTERNAL_KEYS = new Set(['children', 'raw']);

export function labelFor(key: string) {
  return COMMON_LABELS[key] || key;
}

export function isEmptyValue(value: unknown) {
  return value === null || value === undefined || value === '';
}

export function formatDetailValue(value: unknown, key = ''): DetailValue {
  if (isEmptyValue(value)) {
    return { text: EMPTY_TEXT, fullText: EMPTY_TEXT, empty: true, raw: value };
  }
  if (Array.isArray(value)) {
    if (!value.length) return { text: '[]', fullText: '[]', empty: false, raw: value };
    const simple = value.every(item => ['string', 'number', 'boolean'].includes(typeof item));
    const fullText = simple ? value.map(item => String(item)).join(', ') : JSON.stringify(value, null, 2);
    const text = simple ? fullText : `${value.length} 项`;
    return { text, fullText, empty: false, raw: value };
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return { text: '{}', fullText: '{}', empty: false, raw: value };
    return {
      text: `${entries.length} 个字段`,
      fullText: JSON.stringify(value, null, 2),
      empty: false,
      raw: value
    };
  }
  const text = String(value);
  const normalized = text.toLowerCase();
  const statusTone = STATUS_KEYS.has(key) || STATUS_TONES[normalized] ? STATUS_TONES[normalized] : undefined;
  return {
    text: STATUS_LABELS[normalized] || text,
    fullText: text,
    empty: false,
    raw: value,
    statusTone
  };
}

export function detailRowsFromRecord(
  record: Record<string, unknown> | null | undefined,
  preferredKeys: string[] = [],
  options: { excludeKeys?: Iterable<string>; extraRows?: DetailField[] } = {}
) {
  if (!record) return options.extraRows || [];
  const excluded = new Set([...(options.excludeKeys || []), ...INTERNAL_KEYS]);
  const rows: DetailField[] = [];
  const seen = new Set<string>();
  const push = (key: string, value: unknown) => {
    if (seen.has(key) || excluded.has(key)) return;
    seen.add(key);
    rows.push({ key, label: labelFor(key), value: formatDetailValue(value, key) });
  };
  preferredKeys.forEach(key => {
    if (Object.hasOwn(record, key)) push(key, record[key]);
  });
  Object.entries(record).forEach(([key, value]) => push(key, value));
  return [...(options.extraRows || []), ...rows];
}

export function selectionEvidenceRows(primary: SelectionTarget | null, context: SelectionContext) {
  const rows: DetailField[] = [];
  if (primary) {
    rows.push({
      key: 'primary_object',
      label: '主对象',
      value: formatDetailValue(`${primary.kind} / ${primary.id}`, 'primary_object')
    });
  }
  const contextRecord = context as unknown as Record<string, unknown>;
  const coreKeys = new Set([
    'mappingStatus',
    'mappingAuthority',
    'primitiveIds',
    'renderFaceIds',
    'recognizedFeatureIds'
  ]);
  const coreRows: DetailField[] = [
    'mappingStatus',
    'mappingAuthority',
    'primitiveIds',
    'renderFaceIds',
    'recognizedFeatureIds'
  ].flatMap(key => {
    if (!Object.hasOwn(contextRecord, key)) return [];
    const raw = contextRecord[key];
    if (key === 'primitiveIds' && Array.isArray(raw)) {
      return [{ key, label: 'Primitive', value: formatDetailValue(raw.length, key) }];
    }
    return [
      {
        key,
        label: key === 'recognizedFeatureIds' ? '关联 Feature' : labelFor(key),
        value: formatDetailValue(raw, key)
      }
    ];
  });
  const extraRows = detailRowsFromRecord(contextRecord, [], {
    excludeKeys: coreKeys
  }).filter(row => !Array.isArray(row.value.raw) || row.value.raw.length > 0);
  return [...rows, ...coreRows, ...extraRows];
}

export function nativeFeatureRows(
  feature: NativeFeatureRecord | null,
  treeDisplayName?: string,
  parentDisplayName?: string,
  parameterFamily?: string
) {
  if (!feature) return [];
  const extraRows: DetailField[] = [];
  if (treeDisplayName) {
    extraRows.push({ key: 'tree_display_name', label: '名称', value: formatDetailValue(treeDisplayName) });
  }
  if (parentDisplayName) {
    extraRows.push({ key: 'parent_display_name', label: '所属容器', value: formatDetailValue(parentDisplayName) });
  }
  if (parameterFamily) {
    extraRows.push({ key: 'parameter_family', label: '参数族', value: formatDetailValue(parameterFamily) });
  }
  return detailRowsFromRecord(feature, NATIVE_FEATURE_ORDER, {
    excludeKeys: PARAMETER_CONTAINER_KEYS,
    extraRows
  });
}

export function recognizedFeatureRows(feature: CanonicalFeatureRecord | null) {
  return detailRowsFromRecord(feature as unknown as Record<string, unknown> | null, RECOGNIZED_FEATURE_ORDER, {
    excludeKeys: ['typed_payload']
  });
}

export function faceRows(face: Record<string, unknown> | null | undefined) {
  return detailRowsFromRecord(face, FACE_ORDER);
}

export function bomRows(node: Record<string, unknown> | null | undefined) {
  return detailRowsFromRecord(node, BOM_ORDER);
}

export function normalizeParameterRows(source: unknown): ParameterField[] {
  if (!source || typeof source !== 'object') return [];
  if (Array.isArray(source)) {
    return source.map((item, index) => {
      if (item && typeof item === 'object') {
        const record = item as Record<string, unknown>;
        const key = String(record.key ?? record.name ?? record.label ?? `parameter_${index + 1}`);
        const value = Object.hasOwn(record, 'value') ? record.value : record;
        return { key, label: key, value: formatDetailValue(value, key) };
      }
      const key = `parameter_${index + 1}`;
      return { key, label: key, value: formatDetailValue(item, key) };
    });
  }
  return Object.entries(source as Record<string, unknown>).map(([key, value]) => ({
    key,
    label: key,
    value: formatDetailValue(value, key)
  }));
}

export function parameterSourceFor(
  nativeFeature: NativeFeatureRecord | null,
  recognizedFeature: CanonicalFeatureRecord | null
) {
  if (nativeFeature) {
    return nativeFeature.native_feature_parameters || nativeFeature.parameter || nativeFeature.attributes || {};
  }
  if (recognizedFeature) {
    const payload = recognizedFeature.typed_payload || {};
    const geometry = payload.geometry_recognition;
    return geometry && typeof geometry === 'object' ? geometry : payload;
  }
  return {};
}

export function mergeNativeDetail(
  tree: NativeFeatureRecord,
  detail: { node_id?: string; native_feature?: Record<string, unknown> | null; native_feature_status?: string; revision_id?: string; object_id?: string }
): NativeFeatureRecord {
  const semantic = detail.native_feature || {};
  const payload = semantic.native_hole || semantic.native_prism || semantic.native_fillet || semantic.native_chamfer || semantic.native_sketch;
  return {
    ...tree,
    ...semantic,
    feature_id: tree.feature_id,
    display_name: tree.display_name,
    native_feature_parameters: payload && typeof payload === 'object' ? payload as Record<string, unknown> : undefined,
    native_feature_status: detail.native_feature_status || 'not_imported',
    revision_id: detail.revision_id,
    object_id: detail.object_id || tree.attributes?.object_id
  };
}

export function nativeSemanticParameterRows(feature: NativeFeatureRecord | null): ParameterField[] {
  if (!feature?.native_feature_parameters) return [];
  const rows: ParameterField[] = [];
  const visit = (value: Record<string, unknown>, prefix = '') => {
    for (const [name, item] of Object.entries(value)) {
      if (name === 'elements' && feature.native_feature_parameters?.semantic_kind === 'sketch_geometry') continue;
      const key = prefix ? `${prefix}.${name}` : name;
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        visit(item as Record<string, unknown>, key);
      } else {
        const label = labelFor(name);
        const unit = name.endsWith('_mm') ? 'mm' : name.endsWith('_deg') ? '°' : '';
        const formatted = item === null
          ? { text: '未采集 (null)', fullText: 'null', empty: true, raw: item }
          : item === ''
            ? { text: '空字符串', fullText: '""', empty: false, raw: item }
            : formatDetailValue(item, name);
        rows.push({ key, label: `${prefix ? `${labelFor(prefix.split('.').at(-1) || prefix)} · ` : ''}${label}${unit ? ` (${unit})` : ''}`, value: formatted });
      }
    }
  };
  visit(feature.native_feature_parameters);
  return rows;
}

export function nativePropertyValue(field: Api.ComponentBuild.NativePropertyField): DetailValue {
  const status = field.read_status.toLowerCase();
  if (['failed', 'error'].includes(status)) {
    return { text: '读取失败', fullText: `读取失败 (${field.source_api || '来源未知'})`, empty: true, raw: field.raw_value, statusTone: 'danger' };
  }
  if (['unsupported', 'not_supported'].includes(status)) {
    return { text: '不支持', fullText: '不支持', empty: true, raw: field.raw_value, statusTone: 'warning' };
  }
  const value = field.display_value ?? field.raw_value;
  if (value === null || value === undefined) {
    return { text: '未采集 (null)', fullText: 'null', empty: true, raw: value };
  }
  if (value === '') {
    return { text: '空字符串', fullText: '""', empty: false, raw: value };
  }
  return formatDetailValue(value, field.key);
}

export function geometryLinksFor(options: {
  nativeFaceIds: string[];
  recognizedFaceIds: string[];
  faceFeatureIds: string[];
  selectedFace?: { boundary_edge_ids?: string[]; adjacent_face_ids?: string[] } | null;
}) {
  const links: GeometryLink[] = [];
  const pushMany = (ids: string[], kind: string, clickable: boolean) => {
    ids.forEach(id => {
      if (!id || links.some(link => link.id === id && link.kind === kind)) return;
      links.push({ id, kind, clickable, label: `${kind} ${id}` });
    });
  };
  pushMany(options.nativeFaceIds, '面', true);
  pushMany(options.recognizedFaceIds, '面', true);
  pushMany(options.faceFeatureIds, '特征', false);
  pushMany(options.selectedFace?.adjacent_face_ids || [], '相邻面', true);
  pushMany(options.selectedFace?.boundary_edge_ids || [], '边', false);
  return links;
}
