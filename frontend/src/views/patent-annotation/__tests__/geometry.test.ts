import assert from 'node:assert/strict';
import test from 'node:test';
import {
  clamp01,
  clientPointToNormalized,
  createDefaultLeaderPoints,
  normalizePatentAnnotationDocument
} from '../geometry';

test('clamp01 and client coordinates stay normalized', () => {
  assert.equal(clamp01(-2), 0);
  assert.equal(clamp01(3), 1);
  assert.equal(clamp01(Number.NaN), 0);
  assert.deepEqual(clientPointToNormalized(150, 75, { left: 100, top: 50, width: 200, height: 100 }), {
    x: 0.25,
    y: 0.25
  });
  assert.deepEqual(clientPointToNormalized(500, -10, { left: 100, top: 50, width: 200, height: 100 }), {
    x: 1,
    y: 0
  });
});

test('CAD scene points use normalized renderer coordinates', async () => {
  const interaction = (await import('../../cad-model/modules/cad-viewer-interaction').catch(() => ({}))) as {
    normalizeScenePoint?: (
      clientX: number,
      clientY: number,
      rect: { left: number; top: number; width: number; height: number }
    ) => { x: number; y: number };
  };

  assert.equal(typeof interaction.normalizeScenePoint, 'function');
  assert.deepEqual(interaction.normalizeScenePoint?.(150, 125, { left: 100, top: 50, width: 200, height: 100 }), {
    x: 0.25,
    y: 0.75
  });
  assert.deepEqual(interaction.normalizeScenePoint?.(500, -10, { left: 100, top: 50, width: 200, height: 100 }), {
    x: 1,
    y: 0
  });
});

test('default leader flips left near the right edge', () => {
  const right = createDefaultLeaderPoints({ x: 0.5, y: 0.5 });
  assert.ok(right.label.x > 0.5);

  const left = createDefaultLeaderPoints({ x: 0.95, y: 0.5 });
  assert.ok(left.label.x < 0.95);
});

test('import clamps coordinates and preserves string references', () => {
  const result = normalizePatentAnnotationDocument({
    schemaVersion: '0.1',
    sources: [{ id: 's1', kind: 'pdf', fileKey: 'a.pdf:1:2', fileName: 'a.pdf', pageCount: 1 }],
    annotations: [
      {
        id: 'a1',
        sourceId: 's1',
        sourceKind: 'pdf',
        page: 1,
        refNo: 61,
        partName: '',
        anchor: { x: -1, y: 2 },
        elbow: { x: 0.4, y: 0.4 },
        label: { x: 0.6, y: 0.3 },
        visible: true,
        lineWidth: 1.2,
        fontSize: 16
      }
    ]
  });

  assert.equal(result.annotations[0].refNo, '61');
  assert.deepEqual(result.annotations[0].anchor, { x: 0, y: 1 });
});

test('import rejects annotations whose source does not exist', () => {
  assert.throws(
    () =>
      normalizePatentAnnotationDocument({
        schemaVersion: '0.1',
        sources: [],
        annotations: [
          {
            id: 'a1',
            sourceId: 'missing',
            sourceKind: 'pdf',
            page: 1,
            refNo: '1',
            partName: '',
            anchor: { x: 0.1, y: 0.1 },
            elbow: { x: 0.2, y: 0.2 },
            label: { x: 0.3, y: 0.3 },
            visible: true,
            lineWidth: 1.2,
            fontSize: 16
          }
        ]
      }),
    /来源/
  );
});

test('import rejects duplicate ids and an unsupported schema', () => {
  assert.throws(
    () =>
      normalizePatentAnnotationDocument({
        schemaVersion: '0.2',
        sources: [],
        annotations: []
      }),
    /版本/
  );

  assert.throws(
    () =>
      normalizePatentAnnotationDocument({
        schemaVersion: '0.1',
        sources: [
          { id: 's1', kind: 'pdf', fileKey: 'a', fileName: 'a.pdf', pageCount: 1 },
          { id: 's1', kind: 'pdf', fileKey: 'b', fileName: 'b.pdf', pageCount: 1 }
        ],
        annotations: []
      }),
    /重复/
  );
});
