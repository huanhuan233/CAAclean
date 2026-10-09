import type { SelectionTarget } from './viewer-selection';

export interface StepImportNode {
  id: string;
  parentId: string | null;
  label: string;
  entityType: string;
  geometryType: string | null;
  sourceRef: string | null;
  children: StepImportNode[];
}

// STEP 的导入对象是数据库结构实体，不是 CATIA 的建模历史或 BOM 实例。
export function mapStepImportTree(records: Api.Cad.TreeNode[]): StepImportNode[] {
  const visit = (record: Api.Cad.TreeNode): StepImportNode => ({
    id: record.id,
    parentId: record.parent_entity_id,
    label: record.label || record.source_ref || record.entity_type,
    entityType: record.entity_type,
    geometryType: record.geometry_type,
    sourceRef: record.source_ref,
    children: [...record.children]
      .sort((left, right) => (left.sort_order ?? Number.MAX_SAFE_INTEGER) - (right.sort_order ?? Number.MAX_SAFE_INTEGER))
      .map(visit)
  });
  return records.map(visit);
}

export function filterStepImportTree(nodes: StepImportNode[], query: string): StepImportNode[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return nodes;
  return nodes.flatMap(node => {
    const children = filterStepImportTree(node.children, needle);
    const ownMatch = [node.label, node.id, node.sourceRef, node.entityType, node.geometryType]
      .filter(Boolean).some(value => String(value).toLocaleLowerCase().includes(needle));
    return ownMatch || children.length ? [{ ...node, children: ownMatch ? node.children : children }] : [];
  });
}

export function stepImportSelection(node: StepImportNode): SelectionTarget {
  const kind = node.entityType === 'solid' ? 'solid' :
    node.entityType === 'body' ? 'body' : 'step_import_object';
  return {
    kind,
    id: node.id,
    namespace: 'step_render',
    label: node.label,
    raw: {
      id: node.id,
      name: node.label,
      node_type: node.entityType,
      parent_id: node.parentId,
      source_ref: node.sourceRef,
      geometry_type: node.geometryType,
      child_count: node.children.length
    }
  };
}
