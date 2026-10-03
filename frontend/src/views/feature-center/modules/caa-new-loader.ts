import {
  fetchComponentBuildNativeNodeProperties,
  fetchComponentBuildNativeTree
} from '@/service/api/cad';
import type { NativeFeatureRecord } from './native-feature-tree';
import type { NativeChildPage } from './native-tree-loading';

export async function loadCaaNewNativeRecords(
  buildId: string,
  options?: { signal?: AbortSignal; silent?: boolean }
): Promise<NativeFeatureRecord[]> {
  const records: NativeFeatureRecord[] = [];
  let offset: number | null = 0;
  do {
    const response = await fetchComponentBuildNativeTree(buildId, { offset, page_size: 200 }, options);
    if (!response.data) throw new Error('树节点加载失败，请重试');
    for (const root of response.data.roots || []) flattenNativeTreeNode(root, '', records);
    const nextOffset: number | null = response.data.next_offset ?? null;
    if (nextOffset !== null && nextOffset <= offset) throw new Error('树分页游标没有前进');
    offset = nextOffset;
  } while (offset !== null);
  return records;
}

export async function loadCaaNewNativeChildren(
  buildId: string,
  parentId: string,
  options?: { signal?: AbortSignal; silent?: boolean }
): Promise<NativeFeatureRecord[]> {
  const response = await fetchComponentBuildNativeTree(buildId, { parent_id: parentId }, options);
  if (!response.data) return [];
  const records: NativeFeatureRecord[] = [];
  for (const root of response.data.roots || []) flattenNativeTreeNode(root, parentId, records);
  return records;
}

export async function loadCaaNewNativeChildPage(
  buildId: string,
  parentId: string,
  offset: number,
  options?: { signal?: AbortSignal; silent?: boolean }
): Promise<NativeChildPage> {
  const response = await fetchComponentBuildNativeTree(buildId, { parent_id: parentId, offset, page_size: 200 }, options);
  if (!response.data) throw new Error('树节点加载失败，请点击重试');
  const records: NativeFeatureRecord[] = [];
  for (const root of response.data.roots || []) flattenNativeTreeNode(root, parentId, records);
  return { records, nextOffset: response.data.next_offset ?? null };
}

// 仅接受数据库属性接口的成功响应，读取失败不能伪装成空属性。
export async function loadCaaNewNodeProperties(
  buildId: string,
  nodeId: string,
  options?: { signal?: AbortSignal; silent?: boolean }
) {
  const response = await fetchComponentBuildNativeNodeProperties(buildId, nodeId, options);
  if (response.error || !response.data) throw new Error('数据库属性读取失败，请重试');
  return response.data;
}

export function createNativeDetailLoader(fetcher = loadCaaNewNodeProperties) {
  const cache = new Map<string, Api.ComponentBuild.NativeNodeProperties>();
  let generation = 0;
  let activeController: AbortController | null = null;
  return {
    async load(buildId: string, revisionId: string, nodeId: string) {
      const requestGeneration = ++generation;
      activeController?.abort();
      activeController = new AbortController();
      const key = JSON.stringify([buildId, revisionId, nodeId]);
      const cached = cache.get(key);
      if (cached) return cached;
      try {
        const detail = await fetcher(buildId, nodeId, { signal: activeController.signal, silent: true });
        if (requestGeneration !== generation) return null;
        cache.set(key, detail);
        return detail;
      } catch (error) {
        if (requestGeneration !== generation) return null;
        throw error;
      }
    },
    cancel() {
      generation += 1;
      activeController?.abort();
      activeController = null;
    },
    clear() {
      generation += 1;
      activeController?.abort();
      activeController = null;
      cache.clear();
    }
  };
}

function flattenNativeTreeNode(
  node: Api.ComponentBuild.NativeTreeNode,
  parentId: string,
  records: NativeFeatureRecord[]
) {
  records.push({
    feature_id: node.node_id,
    parent_id: parentId || undefined,
    traversal_index: node.source_index,
    native_enumeration_index: node.source_index,
    container_enumeration_index: node.source_index,
    display_name: node.display_name,
    internal_name: node.internal_name,
    native_type: node.node_kind,
    startup_type: node.startup_type,
    tree_path: node.tree_path,
    update_status: node.update_status,
    parameter_value: node.parameter_value,
    attributes: {
      document_id: node.document_id,
      object_id: node.object_id,
      occurrence_id: node.occurrence_id,
      product_occurrence_id: node.product_occurrence_id,
      reference_id: node.reference_id,
      referenced_document_id: node.referenced_document_id,
      presentation_status: node.presentation_status,
      has_properties: node.has_properties,
      property_count: node.property_count,
      has_geometry: node.has_geometry,
      has_topology_mapping: node.has_topology_mapping,
      geometry_ids: node.geometry_ids,
      topology_ids: node.topology_ids,
      child_count: node.child_count,
      has_children: node.has_children
    }
  });
  for (const child of node.children || []) {
    flattenNativeTreeNode(child, node.node_id, records);
  }
}
