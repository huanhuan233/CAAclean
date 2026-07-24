# Patent Annotation MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-usable PDF patent-figure leader annotation editor and a minimal STEP annotation mode at `/patent-annotation`.

**Architecture:** A shared normalized-coordinate annotation store drives a stateless SVG leader overlay and property inspector. PDF and STEP workspaces own only their source loading and viewport interaction; STEP extends the existing `CadViewer` with optional, backward-compatible scene-click and interaction-lock capabilities.

**Tech Stack:** Vue 3, TypeScript, Element Plus, `vue-pdf-embed`, Three.js, OrbitControls, Elegant Router, Node test runner through `tsx`.

## Global Constraints

- Work on branch `feat/patent-annotation-mvp`.
- Do not add backend tables, endpoints, migrations, or PDF upload behavior.
- Do not add Fabric.js, Konva, or another canvas dependency.
- Do not refactor `cad-spec`; only reuse its fit/zoom/pan ideas.
- Persist every 2D point as a finite `[0, 1]` normalized coordinate.
- Keep `refNo` as a string.
- Preserve the existing `CadViewer` `faceClick(entityId)` contract and `/cad-model` behavior.
- Do not implement AI, patent text parsing, automatic extraction, line avoidance, Word/PDF/PNG output, or STEP dynamic reprojection.
- Run only scoped tests, `pnpm typecheck`, and `pnpm build`; do not run repository-wide `lint --fix`.
- Produce two implementation commits: `feat: add pdf patent annotation editor` and `feat: add minimal step annotation mode`.

---

## File Structure

**Create**

- `frontend/src/views/patent-annotation/types.ts`: stable exported document types.
- `frontend/src/views/patent-annotation/geometry.ts`: pure normalized-coordinate helpers and document normalization.
- `frontend/src/views/patent-annotation/composables/usePatentAnnotations.ts`: reactive annotation/source state, selection, persistence, import/export, and future suggestion entrypoint.
- `frontend/src/views/patent-annotation/modules/LeaderOverlay.vue`: shared SVG renderer, selection, and handle dragging.
- `frontend/src/views/patent-annotation/modules/AnnotationInspector.vue`: shared list and property editor.
- `frontend/src/views/patent-annotation/modules/PdfAnnotationWorkspace.vue`: PDF runtime files, pages, stage transform, and creation interaction.
- `frontend/src/views/patent-annotation/modules/StepAnnotationWorkspace.vue`: CAD model flow, Viewer, lock state, and scene-click creation.
- `frontend/src/views/patent-annotation/index.vue`: route page, shared store, mode switch, JSON commands, inspector, and workspace orchestration.
- `frontend/src/views/patent-annotation/__tests__/geometry.test.ts`: pure geometry and normalization tests.
- `frontend/src/views/patent-annotation/__tests__/annotations.test.ts`: source reuse, numbering, editing, clear, persistence, and import tests.

**Modify**

- `frontend/package.json`: add only a scoped `test:patent-annotation` script.
- `frontend/src/router/routes/index.ts`: add the custom top-level route at menu order 4.
- `frontend/src/router/elegant/imports.ts`: generated view import.
- `frontend/src/router/elegant/routes.ts`: generated route declaration.
- `frontend/src/router/elegant/transform.ts`: generated route map entry.
- `frontend/src/typings/elegant-router.d.ts`: generated route types.
- `frontend/src/locales/langs/zh-cn.ts`: add the Chinese route label without changing the existing system title.
- `frontend/src/locales/langs/en-us.ts`: add the English route label.
- `frontend/src/views/cad-model/modules/CadViewer.vue`: optional lock prop and normalized `sceneClick`.

---

### Task 1: Complete PDF Patent Annotation Editor

**Files:**

- Create: `frontend/src/views/patent-annotation/types.ts`
- Create: `frontend/src/views/patent-annotation/geometry.ts`
- Create: `frontend/src/views/patent-annotation/composables/usePatentAnnotations.ts`
- Create: `frontend/src/views/patent-annotation/modules/LeaderOverlay.vue`
- Create: `frontend/src/views/patent-annotation/modules/AnnotationInspector.vue`
- Create: `frontend/src/views/patent-annotation/modules/PdfAnnotationWorkspace.vue`
- Create: `frontend/src/views/patent-annotation/index.vue`
- Create: `frontend/src/views/patent-annotation/__tests__/geometry.test.ts`
- Create: `frontend/src/views/patent-annotation/__tests__/annotations.test.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/src/router/routes/index.ts`
- Modify: `frontend/src/router/elegant/imports.ts`
- Modify: `frontend/src/router/elegant/routes.ts`
- Modify: `frontend/src/router/elegant/transform.ts`
- Modify: `frontend/src/typings/elegant-router.d.ts`
- Modify: `frontend/src/locales/langs/zh-cn.ts`
- Modify: `frontend/src/locales/langs/en-us.ts`

**Interfaces:**

- Produces:

```ts
export type SourceKind = 'pdf' | 'step';

export interface Point2D {
  x: number;
  y: number;
}

export interface PatentSource {
  id: string;
  kind: SourceKind;
  fileKey: string;
  fileName: string;
  pageCount: number;
}

export interface PatentAnnotation {
  id: string;
  sourceId: string;
  sourceKind: SourceKind;
  page: number;
  refNo: string;
  partName: string;
  anchor: Point2D;
  elbow: Point2D;
  label: Point2D;
  visible: boolean;
  lineWidth: number;
  fontSize: number;
  entityId?: string;
  worldPoint?: [number, number, number];
}

export interface PatentAnnotationDocument {
  schemaVersion: '0.1';
  sources: PatentSource[];
  annotations: PatentAnnotation[];
}
```

- Produces geometry/document functions:

```ts
export function clamp01(value: number): number;
export function normalizePoint(point: Point2D): Point2D;
export function clientPointToNormalized(
  clientX: number,
  clientY: number,
  rect: Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>
): Point2D;
export function normalizedPointToPixels(point: Point2D, width: number, height: number): Point2D;
export function createDefaultLeaderPoints(anchor: Point2D): { elbow: Point2D; label: Point2D };
export function normalizePatentAnnotationDocument(input: unknown): PatentAnnotationDocument;
```

- Produces composable contract:

```ts
export const PATENT_ANNOTATION_STORAGE_KEY = 'patent-annotation-draft-v0.1';

export function usePatentAnnotations(options?: {
  storage?: Pick<Storage, 'getItem' | 'setItem'> | null;
  storageKey?: string;
}): {
  document: Ref<PatentAnnotationDocument>;
  selectedAnnotationId: Ref<string>;
  selectedAnnotation: ComputedRef<PatentAnnotation | null>;
  getOrCreateSource(input: Omit<PatentSource, 'id'>): PatentSource;
  updateSource(sourceId: string, patch: Partial<Pick<PatentSource, 'fileName' | 'pageCount'>>): void;
  annotationsFor(sourceId: string, page: number): PatentAnnotation[];
  createAnnotation(input: {
    sourceId: string;
    sourceKind: SourceKind;
    page: number;
    anchor: Point2D;
    entityId?: string;
    worldPoint?: [number, number, number];
  }): PatentAnnotation;
  updateAnnotation(annotationId: string, patch: Partial<PatentAnnotation>): void;
  removeAnnotation(annotationId: string): void;
  clearPage(sourceId: string, page: number): void;
  clearSource(sourceId: string): void;
  replaceDocument(input: unknown): void;
  exportDocument(): PatentAnnotationDocument;
  applySuggestedAnnotations(items: PatentAnnotation[]): void;
};
```

- `LeaderOverlay.vue` consumes `annotations`, `selectedId`, and `interactive`; emits `select(id)` and `update({ id, point, value })`, where point is `'anchor' | 'elbow' | 'label'`.
- `AnnotationInspector.vue` consumes current annotations and selected annotation; emits select, patch, and delete.
- `PdfAnnotationWorkspace.vue` consumes the shared composable methods and current annotations; emits active source/page changes.

- [ ] **Step 1: Write failing pure-logic tests**

Create `geometry.test.ts` with concrete boundary, coordinate, default-placement, and document-normalization expectations:

```ts
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
  assert.deepEqual(
    clientPointToNormalized(150, 75, { left: 100, top: 50, width: 200, height: 100 }),
    { x: 0.25, y: 0.25 }
  );
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
    annotations: [{
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
    }]
  });
  assert.equal(result.annotations[0].refNo, '61');
  assert.deepEqual(result.annotations[0].anchor, { x: 0, y: 1 });
});

test('import rejects annotations whose source does not exist', () => {
  assert.throws(() => normalizePatentAnnotationDocument({
    schemaVersion: '0.1',
    sources: [],
    annotations: [{
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
    }]
  }));
});
```

Create `annotations.test.ts` with an in-memory storage and source/numbering behavior:

```ts
import assert from 'node:assert/strict';
import test from 'node:test';
import { nextTick } from 'vue';
import { usePatentAnnotations } from '../composables/usePatentAnnotations';

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value)
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
  assert.equal(store.createAnnotation({
    sourceId: first.id,
    sourceKind: 'pdf',
    page: 1,
    anchor: { x: 0.2, y: 0.2 }
  }).refNo, '1');
  store.updateAnnotation(store.selectedAnnotationId.value, { refNo: '61' });
  assert.equal(store.createAnnotation({
    sourceId: first.id,
    sourceKind: 'pdf',
    page: 1,
    anchor: { x: 0.4, y: 0.4 }
  }).refNo, '62');
  await nextTick();
  assert.ok(storage.getItem('test')?.includes('"61"'));
});
```

- [ ] **Step 2: Add the scoped test command**

Add this exact script to `frontend/package.json`:

```json
"test:patent-annotation": "tsx --test src/views/patent-annotation/__tests__/*.test.ts"
```

- [ ] **Step 3: Run tests to verify the new modules are missing**

Run:

```bash
cd frontend
pnpm test:patent-annotation
```

Expected: FAIL because `geometry.ts` and `usePatentAnnotations.ts` do not exist.

- [ ] **Step 4: Implement the stable types and pure helpers**

Implement the interfaces exactly as declared above. Use these concrete geometry rules:

```ts
export function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function clientPointToNormalized(clientX: number, clientY: number, rect: RectLike): Point2D {
  if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 };
  return {
    x: clamp01((clientX - rect.left) / rect.width),
    y: clamp01((clientY - rect.top) / rect.height)
  };
}

export function createDefaultLeaderPoints(anchor: Point2D) {
  const direction = anchor.x > 0.78 ? -1 : 1;
  const label = normalizePoint({ x: anchor.x + direction * 0.18, y: anchor.y - 0.12 });
  return {
    elbow: normalizePoint({ x: anchor.x + direction * 0.09, y: label.y }),
    label
  };
}
```

`normalizePatentAnnotationDocument` must:

- require object input, schema `0.1`, and array sources/annotations;
- require unique non-empty source and annotation IDs;
- require `kind/sourceKind` to be `pdf` or `step`;
- require every annotation source to exist and match its kind;
- coerce `refNo` and `partName` to strings;
- clamp page to an integer from 1 through the source page count;
- clamp all points, line width from `0.5` through `8`, and font size from `8` through `72`;
- keep `entityId` only when it is a string;
- keep `worldPoint` only when it is a finite three-number tuple;
- throw an `Error` with a user-presentable Chinese message for structural failures.

- [ ] **Step 5: Implement the reactive annotation store**

Initialize from storage through `normalizePatentAnnotationDocument`; fall back to an empty document only when stored data is absent or invalid. Watch the document deeply and persist JSON. Generate IDs with `crypto.randomUUID()` and a timestamp/random fallback.

The next reference number is calculated across the current source only:

```ts
function nextRefNo(sourceId: string) {
  const numeric = document.value.annotations
    .filter(item => item.sourceId === sourceId && /^\d+$/.test(item.refNo))
    .map(item => Number(item.refNo));
  return String((numeric.length ? Math.max(...numeric) : 0) + 1);
}
```

`getOrCreateSource` must reuse the existing source matching both `kind` and `fileKey`, update its name/page count, and preserve its ID. `updateAnnotation` must normalize any changed points and numeric presentation fields. `applySuggestedAnnotations` must normalize a candidate combined document before appending non-duplicate IDs.

- [ ] **Step 6: Run the scoped tests**

Run:

```bash
cd frontend
pnpm test:patent-annotation
```

Expected: PASS for every geometry and annotation-store test.

- [ ] **Step 7: Implement the shared SVG overlay**

Use an SVG that fills its positioned parent and uses stage pixels as its view box. Convert normalized persisted points with `normalizedPointToPixels` before rendering:

```vue
<svg
  class="leader-overlay"
  :viewBox="`0 0 ${stageWidth} ${stageHeight}`"
  preserveAspectRatio="none"
  @pointerdown.self="emit('select', '')"
>
  <g v-for="annotation in visibleAnnotations" :key="annotation.id">
    <polyline
      :points="leaderPoints(annotation)"
      fill="none"
      vector-effect="non-scaling-stroke"
      :stroke="annotation.id === selectedId ? 'var(--el-color-primary)' : 'var(--el-text-color-primary)'"
      :stroke-width="annotation.lineWidth"
      @pointerdown.stop="emit('select', annotation.id)"
    />
    <circle
      :cx="toPixels(annotation.anchor).x"
      :cy="toPixels(annotation.anchor).y"
      r="3"
      vector-effect="non-scaling-stroke"
    />
    <text
      :x="toPixels(annotation.label).x"
      :y="toPixels(annotation.label).y"
      dominant-baseline="central"
      :font-size="annotation.fontSize"
      @pointerdown.stop="emit('select', annotation.id)"
    >{{ annotation.refNo }}</text>
  </g>
</svg>
```

Render three handles for the selected annotation. On handle pointerdown, capture the pointer on the SVG element; on pointermove, call `clientPointToNormalized` with the SVG bounding rect and emit the relevant point update; release capture on pointerup/cancel. Stop propagation so handle dragging never starts panning or creates a new annotation.

- [ ] **Step 8: Implement the shared inspector**

Use a scrollable list followed by an `ElForm`. Coordinate inputs display `point.x * 100` and write back `value / 100`. Use `ElInput` for `refNo/partName`, `ElInputNumber` for coordinates/line width/font size, `ElSwitch` for visibility, and a danger `ElButton` for delete. Emit partial patches; do not clone the source object into an unsynchronized form.

- [ ] **Step 9: Implement the PDF workspace**

Maintain runtime-only entries:

```ts
interface PdfRuntimeSource {
  sourceId: string;
  fileKey: string;
  file: File;
  objectUrl: string;
}
```

On multi-file selection:

```ts
const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
const source = getOrCreateSource({
  kind: 'pdf',
  fileKey,
  fileName: file.name,
  pageCount: 1
});
runtimeSources.value.push({
  sourceId: source.id,
  fileKey,
  file,
  objectUrl: URL.createObjectURL(file)
});
```

Reject non-PDF files. Deduplicate the runtime set by `fileKey`. Revoke every Object URL on runtime removal and `onBeforeUnmount`.

Place `VuePdfEmbed` and `LeaderOverlay` in the same transformed stage:

```vue
<div
  ref="viewportRef"
  class="pdf-viewport"
  @pointerdown="onViewportPointerDown"
  @pointermove="onViewportPointerMove"
  @pointerup="stopPan"
  @pointercancel="stopPan"
  @wheel.prevent="onWheel"
>
  <div class="pdf-stage" :style="stageStyle">
    <VuePdfEmbed
      ref="pdfRef"
      :source="activeRuntime.objectUrl"
      :page="currentPage"
      @rendered="onPdfRendered"
    />
    <LeaderOverlay
      :annotations="currentAnnotations"
      :selected-id="selectedAnnotationId"
      :stage-width="stageWidth"
      :stage-height="stageHeight"
      @select="selectAnnotation"
      @update="updateLeaderPoint"
    />
  </div>
</div>
```

After rendering, read the rendered canvas with `stageRef.querySelector('canvas')`. Use `canvas.clientWidth/clientHeight` as the CSS stage size; if either is zero, use `getBoundingClientRect().width/height` divided by the current scale. Do not use the DPR-scaled `canvas.width/height`. Keep the stage background white.

Use scale limits `0.1` through `6`. Fit with 16px padding. Wheel zoom must keep the pointer location stable by updating pan around the pointer. Panning starts only for middle button or Space + primary button. Add mode starts only from an explicit button and consumes exactly one ordinary primary click on the overlay; it creates and selects the annotation, then disables itself.

- [ ] **Step 10: Assemble the page and JSON commands**

`index.vue` owns one `usePatentAnnotations()` instance, the active mode, active source/page, selected annotation, and file inputs. Its grid contains the active workspace and `AnnotationInspector`.

Export with a Blob named `patent-annotations.json`:

```ts
const blob = new Blob([JSON.stringify(exportDocument(), null, 2)], { type: 'application/json' });
const url = URL.createObjectURL(blob);
const anchor = window.document.createElement('a');
anchor.href = url;
anchor.download = 'patent-annotations.json';
anchor.click();
URL.revokeObjectURL(url);
```

Import with `file.text()`, `JSON.parse`, and `replaceDocument`; show success/error messages. Clear current page through `ElMessageBox.confirm`, then call `clearPage(activeSourceId, activePage)`.

- [ ] **Step 11: Add the route and generated types**

Add this route after `cadSpecRoute`:

```ts
const patentAnnotationRoute = {
  name: 'patent-annotation',
  path: '/patent-annotation',
  component: 'layout.base$view.patent-annotation',
  meta: {
    title: '专利附图标注',
    icon: 'carbon:draw',
    order: 4
  }
} as unknown as CustomRoute;
```

Append it to `customRoutes` without reordering the first three entries. Add:

```ts
'patent-annotation': '专利附图标注'
```

and:

```ts
'patent-annotation': 'Patent Figure Annotation'
```

Run:

```bash
cd frontend
pnpm gen-route
git diff -- src/router src/typings/elegant-router.d.ts src/locales/langs
```

Expected: only the route/view entries and the two locale keys change. If the generator omits the custom route, manually add the same generated entries following `component-build`.

- [ ] **Step 12: Verify P0 automatically**

Run:

```bash
cd frontend
pnpm test:patent-annotation
pnpm typecheck
pnpm build
```

Expected: all commands exit 0. Fix only files in this task.

- [ ] **Step 13: Smoke-test the PDF workflow**

Start the existing frontend and backend development processes. In `/patent-annotation`:

1. Upload four local PDFs in one selection and switch among them.
2. Change pages and use fit, zoom, wheel, Space+drag, and middle-drag.
3. Create a leader and change its number from `1` to `61`.
4. Edit and drag anchor, elbow, and label.
5. Switch source/page and return.
6. Export JSON, clear the current page, import JSON, and confirm restoration.
7. Refresh and upload the same file, confirming the draft reattaches by `fileKey`.
8. Inspect the console for unhandled Promise errors and verify Object URLs are revoked on removal/unmount.

- [ ] **Step 14: Commit the PDF editor**

Stage only the P0 files listed in this task and inspect the staged diff:

```bash
git add frontend/package.json frontend/src/views/patent-annotation frontend/src/router/routes/index.ts frontend/src/router/elegant/imports.ts frontend/src/router/elegant/routes.ts frontend/src/router/elegant/transform.ts frontend/src/typings/elegant-router.d.ts frontend/src/locales/langs/zh-cn.ts frontend/src/locales/langs/en-us.ts
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add pdf patent annotation editor"
```

Expected: one P0 implementation commit, no backend files and no unrelated generated changes.

---

### Task 2: Add Minimal STEP Annotation Mode

**Files:**

- Modify: `frontend/src/views/cad-model/modules/CadViewer.vue`
- Create: `frontend/src/views/patent-annotation/modules/StepAnnotationWorkspace.vue`
- Modify: `frontend/src/views/patent-annotation/index.vue`
- Modify: `frontend/src/views/patent-annotation/__tests__/annotations.test.ts`

**Interfaces:**

- Consumes all Task 1 annotation types, store methods, overlay, and inspector.
- Extends `CadViewer` with:

```ts
interactionLocked?: boolean;

interface CadSceneClick {
  entityId: string;
  worldPoint: [number, number, number];
  screen: Point2D;
}
```

- Emits both `(e: 'faceClick', entityId: string)` and `(e: 'sceneClick', payload: CadSceneClick)`.
- STEP source key is exactly `cad-revision:${revisionId}` with `pageCount: 1`.

- [ ] **Step 1: Extend the store test for STEP metadata**

Add:

```ts
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
```

- [ ] **Step 2: Run the scoped tests before Viewer work**

Run:

```bash
cd frontend
pnpm test:patent-annotation
```

Expected: PASS because Task 1 already defined the optional STEP fields and creation contract.

- [ ] **Step 3: Add the backward-compatible Viewer contract**

Extend props and emits:

```ts
const props = withDefaults(defineProps<{
  meshes: Api.Cad.Mesh[];
  selectedFaceId?: string;
  highlightFaceIds?: string[];
  patternEvidence?: Api.Cad.PatternEvidence | null;
  interactionLocked?: boolean;
}>(), {
  selectedFaceId: '',
  highlightFaceIds: () => [],
  patternEvidence: null,
  interactionLocked: false
});

const emit = defineEmits<{
  (e: 'faceClick', entityId: string): void;
  (e: 'sceneClick', payload: {
    entityId: string;
    worldPoint: [number, number, number];
    screen: { x: number; y: number };
  }): void;
}>();
```

Watch the lock without altering defaults:

```ts
watch(
  () => props.interactionLocked,
  locked => {
    if (controls) controls.enabled = !locked;
  },
  { immediate: true }
);
```

On raycaster hit:

```ts
const hit = hits[0];
const entityId = hit?.object.userData.entityId;
if (!entityId || !hit) return;
emit('faceClick', entityId);
emit('sceneClick', {
  entityId,
  worldPoint: [hit.point.x, hit.point.y, hit.point.z],
  screen: {
    x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
    y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height))
  }
});
```

Do not prevent the raycast when controls are disabled.

- [ ] **Step 4: Implement the STEP model flow**

`StepAnnotationWorkspace.vue` keeps:

```ts
const models = ref<Api.Cad.ModelSummary[]>([]);
const selectedModelId = ref('');
const selectedRevisionId = ref('');
const status = ref<Api.Cad.ParseStatus | null>(null);
const meshes = ref<Api.Cad.Mesh[]>([]);
const loadingModels = ref(false);
const loadingMeshes = ref(false);
const uploading = ref(false);
const pollTimer = ref<number | null>(null);
const interactionLocked = ref(false);
const addPending = ref(false);
```

Use `fetchCadModels({ page: 1, page_size: 50 })`. On selection, set the current revision, create/reuse:

```ts
getOrCreateSource({
  kind: 'step',
  fileKey: `cad-revision:${revisionId}`,
  fileName: model.name,
  pageCount: 1
});
```

Call `fetchCadRevisionStatus`. For `queued/processing`, poll every 1500ms; for `completed`, stop polling and load `fetchCadMeshes(revisionId, { page: 1, page_size: 5000 })`; for `failed`, stop and show `error_message || status_message`.

Upload through `uploadCadModel(file, file.name.replace(/\.(step|stp)$/i, ''))`, then select its revision and start polling. Reject other extensions. Clear timers on model change and unmount.

- [ ] **Step 5: Implement lock-and-create**

“锁定视角并添加引线” sets `interactionLocked=true` and `addPending=true`. Pass the lock prop to `CadViewer` and place `LeaderOverlay` absolutely over the Viewer canvas.

On `sceneClick`:

```ts
function handleSceneClick(payload: CadSceneClick) {
  if (!addPending.value || !activeSource.value) return;
  const annotation = createAnnotation({
    sourceId: activeSource.value.id,
    sourceKind: 'step',
    page: 1,
    anchor: payload.screen,
    entityId: payload.entityId,
    worldPoint: payload.worldPoint
  });
  selectedAnnotationId.value = annotation.id;
  addPending.value = false;
  interactionLocked.value = true;
}
```

If unlock is requested and the current source has annotations, confirm with:

```ts
await ElMessageBox.confirm(
  '解锁视角会清空当前 STEP 视图的全部标注，是否继续？',
  '解锁视角',
  { type: 'warning' }
);
clearSource(activeSource.value.id);
interactionLocked.value = false;
addPending.value = false;
```

If no annotations exist, unlock immediately.

- [ ] **Step 6: Connect STEP mode to the page**

Render `StepAnnotationWorkspace` when the active source mode is `step`. Keep the same `AnnotationInspector`, import/export buttons, and store instance. Disable “清空当前页” when no active source; for STEP it clears page 1.

When changing from STEP to PDF, stop the STEP poller by unmounting the workspace. Returning to the same STEP revision must reuse its source and annotations.

- [ ] **Step 7: Verify STEP integration automatically**

Run:

```bash
cd frontend
pnpm test:patent-annotation
pnpm typecheck
pnpm build
```

Expected: all commands exit 0.

- [ ] **Step 8: Smoke-test STEP and CAD regression**

With the existing backend:

1. Open `/patent-annotation`, switch to STEP, and select a completed existing model.
2. Confirm meshes load; rotate and zoom before locking.
3. Click “锁定视角并添加引线”, click a face, and confirm one leader appears.
4. Confirm its JSON contains `entityId`, finite `worldPoint`, and normalized screen points.
5. Edit number, part name, and all three points.
6. Request unlock, cancel once, then confirm once and verify only that STEP source's annotations are cleared.
7. Upload a new `.step` or `.stp`, observe status polling, and load meshes after completion.
8. Open `/cad-model`, click faces, rotate, pan, and zoom; confirm behavior is unchanged.

- [ ] **Step 9: Commit STEP mode**

```bash
git add frontend/src/views/cad-model/modules/CadViewer.vue frontend/src/views/patent-annotation/modules/StepAnnotationWorkspace.vue frontend/src/views/patent-annotation/index.vue frontend/src/views/patent-annotation/__tests__/annotations.test.ts
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add minimal step annotation mode"
```

Expected: one P1 implementation commit with no backend changes.

---

### Task 3: Final Acceptance and Handoff

**Files:**

- Verify only; no planned source changes.

**Interfaces:**

- Consumes the completed P0 and P1 page.
- Produces command results and reproducible manual verification steps for the final handoff.

- [ ] **Step 1: Inspect final scope**

Run:

```bash
git status --short
git log -4 --oneline --decorate
git diff main...HEAD --stat
git diff main...HEAD -- backend
```

Expected: clean worktree; design/plan plus two implementation commits; no backend diff.

- [ ] **Step 2: Run final automated verification**

Run:

```bash
cd frontend
pnpm test:patent-annotation
pnpm typecheck
pnpm build
```

Expected: all commands exit 0. Record the exact exit status and any non-failing warnings.

- [ ] **Step 3: Verify cleanup and regressions**

Inspect code paths to confirm:

- every PDF Object URL is revoked;
- every STEP polling timer is cleared on source change/unmount;
- no unhandled Promise-returning event handler remains;
- `CadViewer` defaults keep OrbitControls enabled;
- original `faceClick` still emits for every raycast hit;
- no production code contains sample patent numbers or golden coordinates.

- [ ] **Step 4: Prepare the final handoff**

Report:

- change summary;
- major files;
- exact `test:patent-annotation`, `typecheck`, and `build` results;
- PDF and STEP manual test steps/results;
- known limitations: no automatic recognition and no STEP dynamic reprojection after rotation.
