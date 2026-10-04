import assert from 'node:assert/strict';
import test from 'node:test';
import { anglePointParameters } from '../modules/measurement-parameters';

test('curved angle request sends full precision A/B display seeds', () => {
  const parameters = anglePointParameters('unoriented', [
    { text: '1.1235, 2, 3', seed: [1.123456789, 2, 3], edited: false },
    { text: '4, 5.9877, 6', seed: [4, 5.987654321, 6], edited: false }
  ]);
  assert.deepEqual(parameters, {
    orientation: 'unoriented', seed_point_a: [1.123456789, 2, 3], seed_point_b: [4, 5.987654321, 6]
  });
});

test('explicit angle point is sent as exact location', () => {
  const parameters = anglePointParameters('directed', [
    { text: '1.123456789, 2, 3', seed: [1.1235, 2, 3], edited: true },
    { text: '', seed: null, edited: false }
  ]);
  assert.deepEqual(parameters, { orientation: 'directed', point_a: [1.123456789, 2, 3] });
});
