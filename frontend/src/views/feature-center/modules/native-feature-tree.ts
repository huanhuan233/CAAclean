export type FeatureTreeKind =
  | 'catpart'
  | 'part'
  | 'datum_group'
  | 'datum'
  | 'body'
  | 'geometry_set'
  | 'sketch'
  | 'pad'
  | 'pocket'
  | 'hole'
  | 'fillet'
  | 'chamfer'
  | 'solid_feature'
  | 'parameter'
  | 'system'
  | 'unknown';

export type FeatureTreeCategory = 'all' | 'mapped' | 'sketch' | 'solid' | 'datum';

export interface NativeFeatureRecord {
  feature_id: string;
  parent_id?: string;
  traversal_index?: number;
  native_enumeration_index?: number;
  container_enumeration_index?: number;
  display_name?: string;
  internal_name?: string;
  native_type?: string;
  startup_type?: string;
  container_kind?: string;
  tree_path?: string;
  decoder_id?: string;
  decode_level?: string;
  decode_status?: string;
  update_status?: string;
  attributes?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface FeatureTreeNode {
  id: string;
  parentId?: string;
  name: string;
  displayName: string;
  kind: FeatureTreeKind;
  nativeType?: string;
  sourceRef?: string;
  sequence: number;
  children: FeatureTreeNode[];
  isSystem: boolean;
  isContainer: boolean;
  faceRefs: string[];
  parameters?: Record<string, unknown>;
  raw?: NativeFeatureRecord;
}

export interface FeatureTreeProjection {
  nodes: FeatureTreeNode[];
  expandedKeys: string[];
}

const SYSTEM_TYPES = new Set([
  'catiprtcontainer',
  'catprtcontainer',
  'partspeccontainer',
  'gsminternal',
  'defaultvaluesbag',
  'catcatalogmanager'
]);

const KIND_BY_TYPE: Record<string, FeatureTreeKind> = {
  catdocument: 'catpart',
  mechanicalpart: 'part',
  gsmplane: 'datum',
  origin: 'datum',
  axis: 'datum',
  axis2placement3d: 'datum',
  partbody: 'body',
  body: 'body',
  solidbody: 'body',
  hybridbody: 'geometry_set',
  geometricalset: 'geometry_set',
  sketch: 'sketch',
  sketcher: 'sketch',
  pad: 'pad',
  pocket: 'pocket',
  hole: 'hole',
  fillet: 'fillet',
  edgefillet: 'fillet',
  chamfer: 'chamfer',
  shaft: 'solid_feature',
  groove: 'solid_feature',
  rib: 'solid_feature',
  stiffener: 'solid_feature',
  pattern: 'solid_feature',
  string: 'parameter',
  length: 'parameter',
  angle: 'parameter',
  real: 'parameter',
  integer: 'parameter',
  boolean: 'parameter'
};

const CONTAINER_KINDS = new Set<FeatureTreeKind>(['catpart', 'part', 'datum_group', 'body', 'geometry_set', 'system']);
const SOLID_KINDS = new Set<FeatureTreeKind>(['body', 'pad', 'pocket', 'hole', 'fillet', 'chamfer', 'solid_feature']);

// 用途：只截取文件名，防止 CAA 文档节点把本机绝对路径带入界面。
function baseName(path: string) {
  const parts = path.replace(/\\/g, '/').split('/');
  return parts.at(-1) || path;
}

// 用途：用经验证的 StartUp/原生类型映射展示语义；未知类型保持 unknown，不根据名称猜特征。
function featureKind(record: NativeFeatureRecord): FeatureTreeKind {
  const startup = String(record.startup_type || '').toLowerCase();
  const native = String(record.native_type || '').toLowerCase();
  if (SYSTEM_TYPES.has(startup) || SYSTEM_TYPES.has(native)) return 'system';
  return KIND_BY_TYPE[startup] || KIND_BY_TYPE[native] || 'unknown';
}

function sequenceOf(record: NativeFeatureRecord) {
  return Number(
    record.traversal_index ??
      record.container_enumeration_index ??
      record.native_enumeration_index ??
      Number.MAX_SAFE_INTEGER
  );
}

function sortNodes(nodes: FeatureTreeNode[]) {
  nodes.sort((left, right) => left.sequence - right.sequence || left.id.localeCompare(right.id));
  nodes.forEach(node => sortNodes(node.children));
}

// 用途：从扁平 CAA FeatureRecord 恢复原始父子树，并在 Part 下建立稳定的“基准元素”业务分组。
export function buildNativeFeatureTree(
  records: NativeFeatureRecord[],
  sourceFileName: string,
  faceRefsByFeatureId: Record<string, string[]> = {}
): FeatureTreeNode[] {
  const nodes = new Map<string, FeatureTreeNode>();
  const ordered = [...records].sort(
    (left, right) => sequenceOf(left) - sequenceOf(right) || left.feature_id.localeCompare(right.feature_id)
  );
  ordered.forEach(record => {
    const kind = featureKind(record);
    const rawName = String(record.display_name || record.internal_name || record.feature_id);
    const displayName = kind === 'catpart' ? baseName(sourceFileName || rawName) : baseName(rawName);
    nodes.set(record.feature_id, {
      id: record.feature_id,
      parentId: record.parent_id || undefined,
      name: rawName,
      displayName,
      kind,
      nativeType: String(record.startup_type || record.native_type || '') || undefined,
      sourceRef: String(record.tree_path || record.internal_name || '') || undefined,
      sequence: sequenceOf(record),
      children: [],
      isSystem: kind === 'system',
      isContainer: CONTAINER_KINDS.has(kind),
      faceRefs: [...(faceRefsByFeatureId[record.feature_id] || [])],
      parameters: record.attributes,
      raw: record
    });
  });

  const roots: FeatureTreeNode[] = [];
  ordered.forEach(record => {
    const node = nodes.get(record.feature_id)!;
    const parent = record.parent_id ? nodes.get(record.parent_id) : undefined;
    if (parent && parent.id !== node.id) parent.children.push(node);
    else roots.push(node);
  });
  sortNodes(roots);

  for (const part of nodes.values()) {
    if (part.kind !== 'part') continue;
    const datums = part.children.filter(child => child.kind === 'datum');
    if (!datums.length) continue;
    const datumIds = new Set(datums.map(node => node.id));
    const group: FeatureTreeNode = {
      id: `datum-group:${part.id}`,
      parentId: part.id,
      name: '基准元素',
      displayName: '基准元素',
      kind: 'datum_group',
      sequence: Math.min(...datums.map(node => node.sequence)),
      children: datums,
      isSystem: false,
      isContainer: true,
      faceRefs: []
    };
    datums.forEach(node => {
      node.parentId = group.id;
    });
    part.children = [...part.children.filter(child => !datumIds.has(child.id)), group];
    sortNodes(part.children);
  }

  if (!roots.some(node => node.kind === 'catpart')) {
    return [
      {
        id: `source:${sourceFileName}`,
        name: sourceFileName,
        displayName: baseName(sourceFileName),
        kind: 'catpart',
        sequence: 0,
        children: roots,
        isSystem: false,
        isContainer: true,
        faceRefs: []
      }
    ];
  }
  return roots;
}

function categoryMatches(node: FeatureTreeNode, category: FeatureTreeCategory) {
  if (category === 'all') return true;
  if (category === 'mapped') return node.faceRefs.length > 0;
  if (category === 'sketch') return node.kind === 'sketch';
  if (category === 'solid') return SOLID_KINDS.has(node.kind);
  return node.kind === 'datum' || node.kind === 'datum_group';
}

function textMatches(node: FeatureTreeNode, query: string) {
  if (!query) return true;
  const haystack = [node.displayName, node.nativeType, node.id, node.sourceRef]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase();
  return haystack.includes(query.toLocaleLowerCase());
}

// 用途：隐藏系统节点时提升其业务后代；搜索和分类只裁剪展示副本，不改变原始树或选中 ID。
export function projectFeatureTree(
  source: FeatureTreeNode[],
  options: { showSystem: boolean; query?: string; category?: FeatureTreeCategory }
): FeatureTreeProjection {
  const query = options.query?.trim() || '';
  const category = options.category || 'all';

  function hideSystem(nodes: FeatureTreeNode[]): FeatureTreeNode[] {
    return nodes.flatMap(node => {
      const children = hideSystem(node.children);
      if (node.isSystem && !options.showSystem) return children;
      return [{ ...node, children }];
    });
  }

  function filterNodes(nodes: FeatureTreeNode[]): FeatureTreeNode[] {
    return nodes.flatMap(node => {
      const children = filterNodes(node.children);
      const ownMatch = textMatches(node, query) && categoryMatches(node, category);
      if (!ownMatch && !children.length) return [];
      return [{ ...node, children: ownMatch && query ? hideSystem(node.children) : children }];
    });
  }

  const nodes = filterNodes(hideSystem(source));
  const expandedKeys = flattenFeatureTree(nodes)
    .filter(node => node.children.length > 0)
    .map(node => node.id);
  return { nodes, expandedKeys };
}

export function flattenFeatureTree(nodes: FeatureTreeNode[]): FeatureTreeNode[] {
  const flattened: FeatureTreeNode[] = [];
  const visit = (node: FeatureTreeNode) => {
    flattened.push(node);
    node.children.forEach(visit);
  };
  nodes.forEach(visit);
  return flattened;
}

// 用途：返回纯文本片段供模板使用 mark 渲染，避免 v-html 和转义风险。
export function splitHighlight(text: string, query: string): Array<{ text: string; matched: boolean }> {
  const needle = query.trim();
  if (!needle) return [{ text, matched: false }];
  const index = text.toLocaleLowerCase().indexOf(needle.toLocaleLowerCase());
  if (index < 0) return [{ text, matched: false }];
  return [
    { text: text.slice(0, index), matched: false },
    { text: text.slice(index, index + needle.length), matched: true },
    { text: text.slice(index + needle.length), matched: false }
  ].filter(part => part.text.length > 0);
}
