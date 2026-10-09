// 三种格式共用检视入口，由结果契约选择二维或三维场景。
export function modelViewerLocation(
  buildId: string,
  _revisionId: string,
  sourceFormat: 'STEP' | 'CATPART' | 'CATPRODUCT' | 'DXF' | null | undefined
) {
  if (sourceFormat === 'DXF' || sourceFormat === 'STEP' || sourceFormat === 'CATPART' || sourceFormat === 'CATPRODUCT') {
    return { path: '/feature-center', query: { build_id: buildId } };
  }
  return { path: '/component-build', query: { build_id: buildId, revision_id: _revisionId } };
}
