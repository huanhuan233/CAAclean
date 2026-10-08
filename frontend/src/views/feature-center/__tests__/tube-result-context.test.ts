import assert from 'node:assert/strict';
import test from 'node:test';
import { tubeResultCanOverlay } from '../modules/tube-result-context';

const record = { revision_id: 'REV', geometry_snapshot_id: 'SNAP', result_version: 'RUN', source: 'derived_geometry' };
const run = { revision_id: 'REV', geometry_snapshot_id: 'SNAP', result_version: 'RUN', current_snapshot_status: 'current' };

test('current tube analysis overlays only its matching revision and snapshot', () => {
  assert.equal(tubeResultCanOverlay(record, run, 'REV', 'SNAP'), true);
  assert.equal(tubeResultCanOverlay(record, run, 'REV', 'NEW'), false);
  assert.equal(tubeResultCanOverlay(record, { ...run, current_snapshot_status: 'stale' }, 'REV', 'SNAP'), false);
  assert.equal(tubeResultCanOverlay(record, { ...run, current_snapshot_status: 'unavailable' }, 'REV', 'SNAP'), false);
  assert.equal(tubeResultCanOverlay({ ...record, result_version: 'OLD' }, run, 'REV', 'SNAP'), false);
  assert.equal(tubeResultCanOverlay(record, run, 'OTHER', 'SNAP'), false);
});

test('native capture without a verified display geometry context is not overlaid', () => {
  assert.equal(tubeResultCanOverlay({ revision_id: 'REV', source: 'native_sweep_path' }, null, 'REV', 'SNAP'), false);
});
