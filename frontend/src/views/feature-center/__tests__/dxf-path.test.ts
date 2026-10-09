import assert from 'node:assert/strict';
import test from 'node:test';
import { polylinePath } from '../modules/dxf-path';

test('bulge arcs retain direction, major sweep and closing segment', () => {
  const positive = polylinePath([[0, 0, 0, 0, 1], [2, 0, 0, 0, 0]], true);
  const negative = polylinePath([[0, 0, 0, 0, -1], [2, 0, 0, 0, 0]], true);
  const majorClosing = polylinePath([[0, 0, 0, 0, 0], [2, 0, 0, 0, 2]], true);
  assert.match(positive, /A 1 1 0 0 1 2 0/);
  assert.match(negative, /A 1 1 0 0 0 2 0/);
  assert.match(majorClosing, /A 1\.25 1\.25 0 1 1 0 0/);
});
