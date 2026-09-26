import assert from 'node:assert/strict';
import test from 'node:test';
import { nativeChildPages } from '../modules/native-tree-loading';

test('returns the first page before fetching more; skips system leaves', async () => {
  const calls: string[] = [];
  const pages = nativeChildPages('root', async (parentId, offset) => {
    calls.push(`${parentId}:${offset}`);
    if (parentId === 'root' && offset === 0) return {
      records: [
        { feature_id: 'part', startup_type: 'MechanicalPart', attributes: { has_children: true } },
        { feature_id: 'empty-system', startup_type: 'DefaultValuesBag', attributes: { has_children: false } },
        { feature_id: 'system', startup_type: 'CATIPrtContainer', attributes: { has_children: true } }
      ], nextOffset: 200
    };
    return { records: [{ feature_id: `${parentId}-${offset}` }], nextOffset: null };
  });
  const first = await pages.next();
  assert.equal(first.value?.[0].feature_id, 'part');
  assert.deepEqual(calls, ['root:0']);
  const remainder = [];
  for await (const page of pages) remainder.push(...page);
  assert.deepEqual(calls, ['root:0', 'system:0', 'root:200']);
  assert.equal(remainder.length, 2);
});

test('surfaces a failed page instead of treating it as an empty branch', async () => {
  const pages = nativeChildPages('root', async () => { throw new Error('request failed'); });
  await assert.rejects(pages.next(), /request failed/);
});

test('rejects a stuck pagination cursor and does not loop forever', async () => {
  const pages = nativeChildPages('root', async () => ({ records: [], nextOffset: 0 }));
  await pages.next();
  await assert.rejects(pages.next(), /分页游标/);
});
