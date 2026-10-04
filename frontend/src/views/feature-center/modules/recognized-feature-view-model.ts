import type { CanonicalFeatureRecord, FeatureMeshMap } from './feature-center-bundle';

type StatusTone = 'success' | 'warning' | 'info';

export interface RecognizedFeatureItem {
  key: string;
  featureId: string;
  family: string;
  subtype: string;
  name: string;
  title: string;
  category: string;
  descriptors: string[];
  status: { label: string; tone: StatusTone; raw: string };
  searchText: string;
  canLocate: boolean;
  locateReason: string;
  candidatePreview: boolean;
}

const FAMILY_NAMES: Record<string, string> = {
  fillet: '圆角',
  chamfer: '倒角',
  hole: '孔',
  boss: '凸台',
  pocket: '型腔',
  slot: '槽',
  rib: '筋',
  web: '薄板',
  flange: '缘条'
};

const SUBTYPES: Record<string, { name: string; descriptors: string[] }> = {
  'fillet/constant_radius_straight_edge': {
    name: '圆角',
    descriptors: ['恒定半径', '直边']
  },
  'hole/through_hole': { name: '圆孔', descriptors: ['通孔'] },
  'hole/blind_hole': { name: '圆孔', descriptors: ['盲孔'] },
  'hole/stepped_through_hole': { name: '阶梯孔', descriptors: ['贯穿'] },
  'hole/stepped_blind_hole': { name: '阶梯孔', descriptors: ['盲孔'] },
  'hole/cylindrical_void_candidate': { name: '圆柱空域候选', descriptors: [] },
  'boss/rectangular_straight_wall': { name: '矩形凸台', descriptors: ['直壁'] },
  'boss/circular_straight_wall': { name: '圆形凸台', descriptors: ['直壁'] },
  'pocket/rectangular_straight_wall': {
    name: '矩形型腔',
    descriptors: ['直壁']
  },
  'slot/open_straight_wall': { name: '开放槽', descriptors: ['直壁'] },
  'rib/straight_prismatic_candidate': { name: '直筋候选', descriptors: [] },
  'web/thin_plate_candidate': { name: '薄板候选', descriptors: ['平面配对'] },
  'flange/straight_free_edge_band_candidate': {
    name: '缘条候选',
    descriptors: []
  },
  'chamfer/straight_edge_two_plane': {
    name: '倒角',
    descriptors: ['直边', '两平面支撑']
  },
  'chamfer/circular_hole_mouth_cone': {
    name: '倒角',
    descriptors: ['圆孔口', '锥面']
  }
};

const FAMILY_ORDER = ['fillet', 'chamfer', 'hole', 'rib', 'web', 'boss', 'pocket', 'slot', 'flange'];

function recognitionPayload(feature: CanonicalFeatureRecord): Record<string, unknown> {
  const payload = feature.typed_payload?.geometry_recognition;
  return payload && typeof payload === 'object' && !Array.isArray(payload) ? (payload as Record<string, unknown>) : {};
}

function statusFor(feature: CanonicalFeatureRecord): RecognizedFeatureItem['status'] {
  const payload = recognitionPayload(feature);
  const candidateRole =
    ['rib', 'web', 'flange'].includes(feature.family) && payload.structural_role_status === 'candidate';
  const conflictingClassification =
    payload.classification_status === 'candidate' && feature.review_state === 'auto_verified';
  const candidateSubtype = feature.subtype.endsWith('_candidate');
  if (feature.review_state === 'auto_verified' && (candidateRole || conflictingClassification || candidateSubtype))
    return { label: '状态需核实', tone: 'warning', raw: feature.review_state };
  if (feature.review_state === 'auto_verified')
    return { label: '自动核验', tone: 'success', raw: feature.review_state };
  if (feature.review_state === 'needs_review') return { label: '待复核', tone: 'warning', raw: feature.review_state };
  return { label: '状态未知', tone: 'info', raw: feature.review_state };
}

function canLocate(feature: CanonicalFeatureRecord, mapping: FeatureMeshMap | null): boolean {
  const entry = mapping?.features[feature.feature_center_id];
  if (!entry || (!entry.face_ids.length && !entry.mesh_primitive_ids.length)) return false;
  const range = recognitionPayload(feature).render_range_status;
  return typeof range !== 'string' || range === 'confirmed' || range.startsWith('candidate');
}

export function buildRecognizedFeatureItems(
  records: CanonicalFeatureRecord[],
  revisionId: string,
  mapping: FeatureMeshMap | null
): RecognizedFeatureItem[] {
  const counters = new Map<string, number>();
  return records.map(feature => {
    const knownFamily = FAMILY_NAMES[feature.family];
    const definition = SUBTYPES[`${feature.family}/${feature.subtype}`];
    const name = definition?.name || knownFamily || '未分类特征';
    const descriptors = definition?.descriptors || (knownFamily ? ['其他子类型'] : []);
    const count = (counters.get(name) || 0) + 1;
    counters.set(name, count);
    const trustedName =
      typeof feature.display_name === 'string' && feature.display_name.trim() ? feature.display_name.trim() : '';
    const title = trustedName || `${name} ${String(count).padStart(3, '0')}`;
    const status = statusFor(feature);
    const locatable = canLocate(feature, mapping);
    const mappedRange = mapping?.features[feature.feature_center_id];
    const rangeStatus = recognitionPayload(feature).render_range_status;
    const candidatePreview = locatable && typeof rangeStatus === 'string' && rangeStatus.startsWith('candidate');
    let locateReason = '';
    if (!locatable)
      locateReason = mappedRange ? '当前显示范围不可定位' : '没有当前版本的可信显示映射';
    return {
      key: `${revisionId}:${mapping?.shape_hash || 'no-mapping'}:${feature.feature_center_id}`,
      featureId: feature.feature_center_id,
      family: feature.family,
      subtype: feature.subtype,
      name,
      title,
      category: knownFamily || '未分类',
      descriptors: descriptors.slice(0, 2),
      status,
      searchText: [
        title,
        name,
        knownFamily,
        ...descriptors,
        status.label,
        feature.family,
        feature.subtype,
        feature.feature_center_id,
        trustedName
      ]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase(),
      canLocate: locatable,
      locateReason,
      candidatePreview
    };
  });
}

export function recognizedFeatureCategories(items: RecognizedFeatureItem[]) {
  const present = new Set(items.map(item => item.family));
  const families = [
    ...FAMILY_ORDER.filter(family => present.has(family)),
    ...[...present].filter(family => !FAMILY_ORDER.includes(family)).sort()
  ];
  return [
    { value: 'all', label: '全部' },
    ...families.map(value => ({
      value,
      label: FAMILY_NAMES[value] || `未分类（${value}）`
    }))
  ];
}

export function filterRecognizedFeatureItems(
  items: RecognizedFeatureItem[],
  filters: {
    category: string;
    status: string;
    keyword: string;
  }
): RecognizedFeatureItem[] {
  const query = filters.keyword.trim().toLocaleLowerCase();
  return items.filter(
    item =>
      (filters.category === 'all' || item.family === filters.category) &&
      (filters.status === 'all' || item.status.raw === filters.status) &&
      (!query || item.searchText.includes(query))
  );
}
