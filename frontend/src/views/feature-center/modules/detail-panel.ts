export type DetailGroup =
  | 'part'
  | 'assembly_instance'
  | 'assembly'
  | 'assembly_statistics'
  | 'source'
  | 'positioning'
  | 'feature'
  | 'geometry'
  | 'operations'
  | 'topology';

export interface DetailPanelContext {
  selectionKind?: 'model' | 'feature' | 'geometry';
  assemblyMode: 'none' | 'single_part' | 'assembly';
  nodeType?: 'assembly' | 'subassembly' | 'part' | 'body' | 'solid' | 'root' | 'imported_object';
  hasParent?: boolean;
  sourceFormat: 'STEP' | 'CATPART' | 'CATPRODUCT';
  nativeFeatureAvailable?: boolean;
  featureFaceMappingAvailable?: boolean;
  geometryHasLinkedFeature?: boolean;
}

export interface DetailPanelLayout {
  groups: DetailGroup[];
  featureLinkLabel: string;
  featureLinkEnabled: boolean;
}

// 用途：根据真实对象类型和装配契约决定右侧分组；界面的 BOM 显隐状态不参与业务判断。
export function buildDetailPanelLayout(context: DetailPanelContext): DetailPanelLayout {
  const featureLinkLabel = context.sourceFormat === 'CATPART' || context.sourceFormat === 'CATPRODUCT'
    ? '查看原生特征与关联面'
    : '查看识别特征与关联面';
  const featureLinkEnabled = Boolean(
    context.featureFaceMappingAvailable
    && (context.sourceFormat === 'STEP' || context.nativeFeatureAvailable)
  );

  if (context.selectionKind === 'feature') {
    return { groups: ['feature', 'operations', 'topology'], featureLinkLabel, featureLinkEnabled };
  }
  if (context.selectionKind === 'geometry') {
    const groups: DetailGroup[] = [];
    // 用途：只有反向映射真实存在时才在几何详情中展示关联特征，不能凭 Face 名称伪造关系。
    if (context.geometryHasLinkedFeature) groups.push('feature');
    groups.push('geometry', 'operations', 'topology');
    return { groups, featureLinkLabel, featureLinkEnabled };
  }

  if (
    context.nodeType === 'assembly'
    || context.nodeType === 'subassembly'
    || (context.nodeType === 'root' && context.assemblyMode === 'assembly')
  ) {
    const groups: DetailGroup[] = ['assembly', 'assembly_statistics'];
    if (context.nodeType === 'subassembly' && context.hasParent) groups.push('positioning');
    groups.push('operations', 'topology');
    return { groups, featureLinkLabel, featureLinkEnabled };
  }

  const groups: DetailGroup[] = ['part'];
  if (context.assemblyMode === 'assembly' && context.hasParent) groups.push('assembly_instance');
  groups.push('source');
  if (context.assemblyMode === 'assembly' && context.hasParent) groups.push('positioning');
  groups.push('operations', 'topology');
  return { groups, featureLinkLabel, featureLinkEnabled };
}
