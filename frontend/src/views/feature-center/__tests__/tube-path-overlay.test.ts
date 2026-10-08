import assert from 'node:assert/strict';
import test from 'node:test';
import { sampleTubeSegment } from '../modules/tube-path-overlay';

test('samples a true finite 270 degree arc rather than a three point polyline', () => {
    const points = sampleTubeSegment({ kind: 'arc', start_mm: [10, 0, 0], end_mm: [0, -10, 0],
      center_mm: [0, 0, 0], plane_normal: [0, 0, 1], radius_mm: 10, bend_deg: 270 });
  assert.ok(points.length > 16);
  assert.deepEqual(points[0].toArray(), [10, 0, 0]);
  assert.ok(Math.abs(points.at(-1)!.distanceTo(points[0]) - Math.sqrt(200)) < 1e-8);
  assert.ok(points.every(point => Math.abs(point.length() - 10) < 1e-8));
});

test('rejects arcs whose reported endpoint conflicts with the analytic geometry', () => {
  assert.deepEqual(sampleTubeSegment({ kind: 'arc', start_mm: [10, 0, 0], end_mm: [0, 10, 0],
    center_mm: [0, 0, 0], plane_normal: [0, 0, 1], radius_mm: 10, bend_deg: 270 }), []);
});
