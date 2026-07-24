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
