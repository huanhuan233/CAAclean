// STEP 与 CATIA 产物共用 Feature Center Viewer；构件库本身不承载三维视图。
export function modelViewerLocation(
  buildId: string,
  _revisionId: string,
  sourceFormat: 'STEP' | 'CATPART' | 'CATPRODUCT' | null | undefined
) {
  if (sourceFormat === 'STEP' || sourceFormat === 'CATPART' || sourceFormat === 'CATPRODUCT') {
    return { path: '/feature-center', query: { build_id: buildId } };
  }
  return { path: '/component-build', query: { build_id: buildId, revision_id: _revisionId } };
}
