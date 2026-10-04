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

test('captured display seed retains full precision for each angle reference', () => {
  const session = createMeasurementSession(async () => ({ status: 'success', values: {} }));
  session.start('angle');
  session.capture({ revision_id: 'R', geometry_snapshot_id: 'S', entity_id: 'A' }, [1.123456789, 2, 3]);
  session.capture({ revision_id: 'R', geometry_snapshot_id: 'S', entity_id: 'B' }, [4, 5.987654321, 6]);
  assert.deepEqual(session.seedPoints.value, [[1.123456789, 2, 3], [4, 5.987654321, 6]]);
});
