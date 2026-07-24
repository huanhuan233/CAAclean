import assert from 'node:assert/strict';
import test from 'node:test';
import { nextTick } from 'vue';
import { usePatentAnnotations } from '../composables/usePatentAnnotations';

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

  assert.throws(() => store.replaceDocument({ schemaVersion: '0.2', sources: [], annotations: [] }));
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
