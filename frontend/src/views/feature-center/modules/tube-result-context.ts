export function tubeResultCanOverlay(
  record: Record<string, unknown>,
  run: Record<string, unknown> | null,
  currentRevisionId: string | undefined,
  currentSnapshotId: string | undefined
): boolean {
  if (!run || !currentRevisionId || !currentSnapshotId || record.source !== 'derived_geometry') return false;
  return run.current_snapshot_status === 'current' &&
    run.revision_id === currentRevisionId && record.revision_id === currentRevisionId &&
    run.geometry_snapshot_id === currentSnapshotId && record.geometry_snapshot_id === currentSnapshotId &&
    Boolean(run.result_version) && record.result_version === run.result_version;
}
