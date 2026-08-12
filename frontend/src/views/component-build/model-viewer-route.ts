// 用途：按真实源格式决定页面身份；STEP 属于 CAD 模型解析，CATPart 属于 Feature Center。
export function modelViewerLocation(
  buildId: string,
  revisionId: string,
  sourceFormat: 'STEP' | 'CATPART' | 'CATPRODUCT' | null | undefined
) {
  if (sourceFormat === 'CATPART' || sourceFormat === 'CATPRODUCT') {
    return { path: '/feature-center', query: { build_id: buildId } };
  }
  return { path: '/cad-model', query: { build_id: buildId, revision_id: revisionId } };
}
