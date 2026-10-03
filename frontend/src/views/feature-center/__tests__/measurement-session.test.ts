import assert from 'node:assert/strict';
import test from 'node:test';
import { createMeasurementSession } from '../modules/measurement-session';

test('A/B measurement does not replace the main selection and stale responses are discarded', async () => {
  let resolveFirst!: (value: { status: string; values: Record<string, unknown> }) => void;
  const first = new Promise<{ status: string; values: Record<string, unknown> }>(resolve => { resolveFirst = resolve; });
  const session = createMeasurementSession(async () => first);
  session.start('distance');
  session.capture({ revision_id: 'R', geometry_snapshot_id: 'S', entity_id: 'A' });
  session.capture({ revision_id: 'R', geometry_snapshot_id: 'S', entity_id: 'B' });
  const pending = session.calculate('build');
  session.clear();
  resolveFirst({ status: 'success', values: { distance_mm: 4 } });
  await pending;
  assert.equal(session.result.value, null);
  assert.equal(session.operation.value, 'idle');
});
