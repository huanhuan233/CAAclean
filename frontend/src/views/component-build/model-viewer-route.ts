// 用途：按真实源格式决定页面身份；CATIA native 进入 Feature Center，其余留在零件库。
export function modelViewerLocation(
  buildId: string,
  revisionId: string,
  sourceFormat: 'STEP' | 'CATPART' | 'CATPRODUCT' | null | undefined
) {
  if (sourceFormat === 'CATPART' || sourceFormat === 'CATPRODUCT') {
    return { path: '/feature-center', query: { build_id: buildId } };
  }
  return { path: '/component-build', query: { build_id: buildId, revision_id: revisionId } };
}
