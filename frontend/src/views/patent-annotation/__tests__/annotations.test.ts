import assert from 'node:assert/strict';
import test from 'node:test';
import { nextTick } from 'vue';
import { usePatentAnnotations } from '../composables/usePatentAnnotations';
import { buildAutoAnnotationSuggestions } from '../composables/usePatentAutoAnnotation';

function memoryStorage() {
  const values = new Map<string, string>();

  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    }
  };
}

test('same fileKey reuses the source and numeric refs advance', async () => {
  const storage = memoryStorage();
  const store = usePatentAnnotations({ storage, storageKey: 'test' });
  const first = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'a.pdf:100:123',
    fileName: 'a.pdf',
    pageCount: 1
  });
  const same = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'a.pdf:100:123',
    fileName: 'a.pdf',
    pageCount: 4
  });

  assert.equal(first.id, same.id);
  assert.equal(same.pageCount, 4);

  const annotation = store.createAnnotation({
    sourceId: first.id,
    sourceKind: 'pdf',
    page: 1,
    anchor: { x: 0.2, y: 0.2 }
  });
  assert.equal(annotation.refNo, '1');

  store.updateAnnotation(annotation.id, { refNo: '61' });
  assert.equal(
    store.createAnnotation({
      sourceId: first.id,
      sourceKind: 'pdf',
      page: 1,
      anchor: { x: 0.4, y: 0.4 }
    }).refNo,
    '62'
  );

  await nextTick();
  assert.ok(storage.getItem('test')?.includes('"61"'));
});

test('rebinding a saved PDF does not reduce its known page count', () => {
  const store = usePatentAnnotations({ storage: null });
  const source = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'manual.pdf:100:456',
    fileName: 'manual.pdf',
    pageCount: 8
  });

  const rebound = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'manual.pdf:100:456',
    fileName: 'manual.pdf',
    pageCount: 1
  });

  assert.equal(rebound.id, source.id);
  assert.equal(rebound.pageCount, 8);
});

test('clearPage removes only the selected source and page', () => {
  const store = usePatentAnnotations({ storage: null });
  const source = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'a.pdf:1:2',
    fileName: 'a.pdf',
    pageCount: 2
  });
  store.createAnnotation({
    sourceId: source.id,
    sourceKind: 'pdf',
    page: 1,
    anchor: { x: 0.2, y: 0.2 }
  });
  store.createAnnotation({
    sourceId: source.id,
    sourceKind: 'pdf',
    page: 2,
    anchor: { x: 0.4, y: 0.4 }
  });

  store.clearPage(source.id, 1);

  assert.equal(store.annotationsFor(source.id, 1).length, 0);
  assert.equal(store.annotationsFor(source.id, 2).length, 1);
});

test('replaceDocument does not mutate the current draft when validation fails', () => {
  const store = usePatentAnnotations({ storage: null });
  const source = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'a.pdf:1:2',
    fileName: 'a.pdf',
    pageCount: 1
  });

  assert.throws(() => store.replaceDocument({ schemaVersion: '9.9', sources: [], annotations: [] }));
  assert.equal(store.document.value.sources[0].id, source.id);
});

test('step annotations retain entity and world point metadata', () => {
  const store = usePatentAnnotations({ storage: null });
  const source = store.getOrCreateSource({
    kind: 'step',
    fileKey: 'cad-revision:rev-1',
    fileName: 'pump-body',
    pageCount: 1
  });

  const annotation = store.createAnnotation({
    sourceId: source.id,
    sourceKind: 'step',
    page: 1,
    anchor: { x: 0.25, y: 0.75 },
    entityId: 'face-12',
    worldPoint: [1, 2, 3]
  });

  assert.equal(annotation.entityId, 'face-12');
  assert.deepEqual(annotation.worldPoint, [1, 2, 3]);
});

test('step runtime classifies files and revision states', async () => {
  const runtime = (await import('../step-runtime').catch(() => ({}))) as {
    isStepFileName?: (fileName: string) => boolean;
    revisionAction?: (status: Api.Cad.ParseStatusValue | undefined, requestFailed?: boolean) => string;
    shouldLockStepView?: (annotationCount: number) => boolean;
  };

  assert.equal(typeof runtime.isStepFileName, 'function');
  assert.equal(typeof runtime.revisionAction, 'function');
  assert.equal(typeof runtime.shouldLockStepView, 'function');
  assert.equal(runtime.isStepFileName?.('pump.STEP'), true);
  assert.equal(runtime.isStepFileName?.('pump.stp'), true);
  assert.equal(runtime.isStepFileName?.('pump.pdf'), false);
  assert.equal(runtime.revisionAction?.('uploaded'), 'poll');
  assert.equal(runtime.revisionAction?.('queued'), 'poll');
  assert.equal(runtime.revisionAction?.('processing'), 'poll');
  assert.equal(runtime.revisionAction?.('completed'), 'load');
  assert.equal(runtime.revisionAction?.('failed'), 'stop');
  assert.equal(runtime.revisionAction?.('deleted'), 'stop');
  assert.equal(runtime.revisionAction?.('processing', true), 'stop');
  assert.equal(runtime.revisionAction?.(undefined), 'stop');
  assert.equal(runtime.shouldLockStepView?.(0), false);
  assert.equal(runtime.shouldLockStepView?.(2), true);
});

test('auto suggestion replacement preserves manual conflicts and unrelated pages', () => {
  const store = usePatentAnnotations({ storage: null });
  const source = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'a.pdf:1:2',
    fileName: 'a.pdf',
    pageCount: 2
  });
  const other = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'b.pdf:1:2',
    fileName: 'b.pdf',
    pageCount: 1
  });

  const manual = store.createAnnotation({ sourceId: source.id, sourceKind: 'pdf', page: 1, anchor: { x: 0.1, y: 0.1 } });
  store.updateAnnotation(manual.id, { refNo: '1', partName: 'manual shell' });
  store.applySuggestedAnnotations([
    suggested('old-auto-1', source.id, 1, '1'),
    suggested('old-auto-2', source.id, 1, '2'),
    suggested('other-page-auto', source.id, 2, '2'),
    suggested('other-source-auto', other.id, 1, '2')
  ]);

  const result = store.applySuggestedAnnotations(
    [suggested('new-auto-1', source.id, 1, '1'), suggested('new-auto-2', source.id, 1, '2'), suggested('new-auto-3', source.id, 1, '3')],
    { sourceId: source.id, page: 1, replaceAuto: true }
  );

  const pageRefs = store.annotationsFor(source.id, 1).map(item => `${item.origin}:${item.refNo}:${item.id}`).sort();
  assert.deepEqual(pageRefs, [`automatic:2:new-auto-2`, `automatic:3:new-auto-3`, `manual:1:${manual.id}`].sort());
  assert.equal(store.annotationsFor(source.id, 2).length, 1);
  assert.equal(store.annotationsFor(other.id, 1).length, 1);
  assert.deepEqual(result, { added: 2, skippedManualRefs: ['1'] });
});

test('acceptPageAutoAnnotations accepts only review automatic annotations on the page', () => {
  const store = usePatentAnnotations({ storage: null });
  const source = store.getOrCreateSource({
    kind: 'pdf',
    fileKey: 'a.pdf:1:2',
    fileName: 'a.pdf',
    pageCount: 2
  });

  store.applySuggestedAnnotations([
    suggested('review-1', source.id, 1, '1', 'review'),
    suggested('accepted-2', source.id, 1, '2', 'accepted'),
    suggested('review-other-page', source.id, 2, '3', 'review')
  ]);

  assert.equal(store.acceptPageAutoAnnotations(source.id, 1), 1);
  assert.equal(store.document.value.annotations.find(item => item.id === 'review-1')?.reviewState, 'accepted');
  assert.equal(store.document.value.annotations.find(item => item.id === 'review-other-page')?.reviewState, 'review');
});

function suggested(id: string, sourceId: string, page: number, refNo: string, reviewState = 'review') {
  return {
    id,
    sourceId,
    sourceKind: 'pdf' as const,
    page,
    refNo,
    partName: `part-${refNo}`,
    anchor: { x: 0.2, y: 0.2 },
    elbow: { x: 0.3, y: 0.2 },
    label: { x: 0.4, y: 0.2 },
    visible: true,
    lineWidth: 1.2,
    fontSize: 16,
    origin: 'automatic' as const,
    reviewState: reviewState as 'review' | 'accepted' | 'rejected',
    confidence: 0.8
  };
}

test('buildAutoAnnotationSuggestions snaps, lays out, and excludes rejected items', () => {
  const data = new Uint8ClampedArray(10 * 10 * 4);
  data.fill(255);
  for (let index = 3; index < data.length; index += 4) data[index] = 255;
  const offset = (6 * 10 + 7) * 4;
  data[offset] = 0;
  data[offset + 1] = 0;
  data[offset + 2] = 0;

  const suggestions = buildAutoAnnotationSuggestions({
    sourceId: 's1',
    sourceKind: 'pdf',
    page: 1,
    components: [
      { ref_no: '1', name: 'shell' },
      { ref_no: '2', name: 'cover' }
    ],
    localization: {
      warnings: [],
      items: [
        {
          ref_no: '1',
          visible: true,
          confidence: 0.8,
          reason: 'visible',
          anchor: { x: 0.68, y: 0.6 },
          bbox: { x_min: 0.1, y_min: 0.2, x_max: 0.3, y_max: 0.4 },
          review_state: 'review'
        },
        {
          ref_no: '2',
          visible: true,
          confidence: 0.2,
          reason: 'hidden',
          anchor: { x: 0.2, y: 0.2 },
          bbox: null,
          review_state: 'rejected'
        }
      ]
    },
    imageData: { width: 10, height: 10, data } as ImageData,
    modelName: 'vision-test'
  });

  assert.equal(suggestions.length, 1);
  assert.equal(suggestions[0].origin, 'automatic');
  assert.equal(suggestions[0].reviewState, 'review');
  assert.equal(suggestions[0].partName, 'shell');
  assert.equal(suggestions[0].anchor.x, 7 / 9);
  assert.equal(suggestions[0].modelName, 'vision-test');
});
