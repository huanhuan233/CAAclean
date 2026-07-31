# Live YAML ComponentSpec Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task by task.

**Goal:** Make an uploaded YAML document the editable ComponentSpec source so arbitrary fields become editable controls, field edits update the YAML preview immediately, and the complete YAML document survives save and reopen.

**Architecture:** Introduce a backward-compatible ComponentSpec document envelope in the backend and a YAML AST-backed working document in the frontend. The backend validates that submitted YAML and structured data are equivalent before persistence. The frontend parses uploads locally, merges inferred fields with known template metadata by path, updates the YAML AST on each field edit, and submits the structured value plus preserved YAML text.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy JSONB, `ruamel.yaml`, Vue 3, TypeScript, Element Plus, `yaml@2.8.3`, Node test runner via `tsx`.

## Global Constraints

- Use `D:\anaconda\envs\3dcad\python.exe` for every backend test and Python command.
- Install the browser-side YAML dependency with pnpm in `frontend`; do not install it into Conda.
- Do not add a database column or migration. Store the new document envelope in the existing JSONB `data` column.
- Preserve old plain-data drafts and all existing API consumers.
- Preserve YAML comments, key order, scalar quoting, and unknown fields wherever the edited node does not require replacement.
- Follow red-green-refactor for each behavior change.
- Do not commit unrelated workspace changes.

---

## Task 1: Define and validate the backend document envelope

**Files:**

- Create: `backend/app/component_builds/component_spec_document.py`
- Modify: `backend/app/component_builds/schemas.py`
- Test: `backend/tests/test_component_spec_document.py`

**Step 1: Write failing document helper tests**

Cover:

- unpacking an old plain-data draft;
- packing `data`, YAML text, and `source_filename`;
- parsing valid mapping-root YAML with comments;
- rejecting malformed YAML and non-mapping roots;
- rejecting YAML whose parsed value differs from submitted `data`;
- treating equivalent mappings and scalar values as equal.

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_component_spec_document.py -q
```

Expected: FAIL because the document helper does not exist.

**Step 2: Implement the smallest document helper**

Add:

- `DOCUMENT_FORMAT = "component_spec_document_v1"`;
- a typed unpacked document value;
- `unpack_component_spec_document(...)`;
- `pack_component_spec_document(...)`;
- `validate_component_spec_yaml(...)`.

Use `ruamel.yaml` safe parsing for validation. Raise a dedicated validation exception with a concise user-facing message.

**Step 3: Extend the request schema**

Keep `data` required and add:

- `yaml: str | None = None`;
- `source_filename: str | None = None`.

**Step 4: Run the focused tests**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```powershell
git add backend/app/component_builds/component_spec_document.py backend/app/component_builds/schemas.py backend/tests/test_component_spec_document.py
git commit -m "feat: validate ComponentSpec YAML documents"
```

---

## Task 2: Persist and serve complete YAML documents compatibly

**Files:**

- Modify: `backend/app/component_builds/router.py`
- Modify: `backend/app/component_builds/service.py`
- Modify: `backend/tests/test_component_build_api.py`
- Modify: `backend/tests/test_component_build_service.py`

**Step 1: Write failing API and service tests**

Cover:

- GET of an old draft returns normalized `data`, rendered `yaml`, and `source_filename: null`;
- PUT accepts and returns a custom YAML document with an unknown field and comment;
- a later GET returns the exact saved YAML text and filename;
- PUT returns 422 and does not mutate the draft when YAML and data differ;
- fusion reads envelope `data`, preserves unknown/manual values, and saves a valid envelope;
- preview remains compatible with clients that submit only `data`.

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_component_build_api.py backend/tests/test_component_build_service.py -q
```

Expected: new assertions FAIL.

**Step 2: Wire request payloads through the router**

Pass `data`, `yaml`, and `source_filename` to save and preview services. Translate the dedicated document validation exception into HTTP 422 without writing a draft.

**Step 3: Update service read/save/preview/fusion behavior**

- GET: unpack old or new storage; render template YAML only for old drafts or blank data.
- PUT: validate supplied YAML against `data`; pack and persist the document envelope.
- Preview: return supplied valid YAML when present, otherwise keep template rendering behavior.
- Fusion: unpack current data, preserve unknown fields, normalize known fields without dropping unknowns, and save a new system-generated document envelope.
- Keep tree status logic based on draft existence unchanged.

**Step 4: Run focused backend regression tests**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_component_spec_document.py backend/tests/test_component_build_api.py backend/tests/test_component_build_service.py backend/tests/test_component_spec_fusion.py -q
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add backend/app/component_builds/router.py backend/app/component_builds/service.py backend/tests/test_component_build_api.py backend/tests/test_component_build_service.py
git commit -m "feat: persist live ComponentSpec YAML"
```

---

## Task 3: Build the frontend YAML working-document core

**Files:**

- Modify: `frontend/package.json`
- Modify: `pnpm-lock.yaml`
- Create: `frontend/src/views/component-build/yaml-working-document.ts`
- Create: `frontend/src/views/component-build/__tests__/yaml-working-document.test.ts`

**Step 1: Add the direct frontend dependency**

Run:

```powershell
pnpm add yaml@2.8.3
```

from `frontend`.

**Step 2: Write failing pure TypeScript tests**

Cover:

- parsing a mapping-root YAML document;
- returning line/column details for malformed YAML;
- rejecting sequence/scalar roots without replacing an existing document;
- inferring object, object-array, scalar-array, string, number, boolean, null, and generic editors;
- merging known template metadata by exact field path;
- updating a scalar by path while retaining comments, order, and unrelated quoting;
- replacing object and array nodes;
- exporting current YAML and plain structured data.

Run:

```powershell
pnpm exec tsx --test src/views/component-build/__tests__/yaml-working-document.test.ts
```

Expected: FAIL because the working-document module does not exist.

**Step 3: Implement the AST-backed working document**

Use `parseDocument` from `yaml`. Expose small pure operations:

- parse/import;
- schema inference;
- template-metadata merge;
- path update;
- YAML serialization;
- plain-data export.

Avoid component or browser dependencies so this module remains deterministic and easy to test.

**Step 4: Run the focused tests**

Run the same `tsx --test` command and expect PASS.

**Step 5: Commit**

```powershell
git add frontend/package.json pnpm-lock.yaml frontend/src/views/component-build/yaml-working-document.ts frontend/src/views/component-build/__tests__/yaml-working-document.test.ts
git commit -m "feat: add YAML working document core"
```

---

## Task 4: Make recursive fields report exact edit paths

**Files:**

- Modify: `frontend/src/views/component-build/modules/ComponentSpecFieldEditor.vue`
- Create: `frontend/src/views/component-build/component-spec-field-events.ts`
- Create: `frontend/src/views/component-build/__tests__/component-spec-field-events.test.ts`

**Step 1: Write failing field-event tests**

Extract path composition and immutable data update into a pure helper. Test nested objects, object-array indices, scalar arrays, and root replacements.

Run:

```powershell
pnpm exec tsx --test src/views/component-build/__tests__/component-spec-field-events.test.ts
```

Expected: FAIL because the helper does not exist.

**Step 2: Implement path-aware event bubbling**

The recursive editor must emit:

```ts
field-change: [path: Array<string | number>, value: unknown]
```

Each recursive level prefixes its object key or array index. Preserve the existing `update:modelValue` event for compatibility.

**Step 3: Run focused tests and a targeted Vue typecheck**

Run the field-event tests, then a temporary targeted `vue-tsc` configuration covering the changed component and its imports. Delete the temporary configuration afterward.

**Step 4: Commit**

```powershell
git add frontend/src/views/component-build/modules/ComponentSpecFieldEditor.vue frontend/src/views/component-build/component-spec-field-events.ts frontend/src/views/component-build/__tests__/component-spec-field-events.test.ts
git commit -m "feat: emit ComponentSpec field paths"
```

---

## Task 5: Replace preview-only upload with a live editor document

**Files:**

- Modify: `frontend/src/views/component-build/modules/ComponentYamlPreview.vue`
- Modify: `frontend/src/views/component-build/modules/ComponentLibraryDialog.vue`
- Modify: `frontend/src/views/component-build/index.vue`
- Modify: the existing ComponentSpec API type/request module located by `fetchComponentSpec`
- Modify: `frontend/src/views/component-build/component-spec-loader.ts`
- Modify: `frontend/src/views/component-build/__tests__/component-spec-loader.test.ts`

**Step 1: Write failing state and loader tests**

Cover:

- loading a persisted YAML document;
- falling back from old API data to generated system YAML;
- importing YAML replaces fields and current preview only after successful parsing;
- field edits update the current preview immediately;
- save payload includes `data`, `yaml`, and `source_filename`;
- system/current preview switching;
- fusion refresh creates a new system baseline.

Keep state transitions in pure helpers where practical so they are testable without mounting Element Plus.

**Step 2: Redesign the preview component**

- Remove the localStorage-only YAML path.
- Emit uploaded filename and text to the dialog.
- Show explicit `系统生成` and `当前编辑` tabs.
- Display parse errors with line/column.
- Keep YAML visible and scrollable during edits.

**Step 3: Make the dialog own one working document**

- Parse persisted or uploaded YAML into the AST-backed document.
- Generate dynamic editable fields from its inferred schema.
- Merge known template labels and constraints by path.
- Apply `field-change` events directly to the YAML AST.
- Update the right preview synchronously.
- Track dirty, loading, saved, and source filename state.
- Do not replace the document when an upload fails.

**Step 4: Update parent and API wiring**

- Load `data`, `yaml`, `source_filename`, and template schema.
- Save the complete working document.
- Keep preview API compatibility, but do not call the backend for every keystroke.
- Refresh both system baseline and current document after fusion.
- Keep offline fallback behavior explicit.

**Step 5: Run frontend tests**

Run:

```powershell
pnpm exec tsx --test src/views/component-build/__tests__/component-spec-loader.test.ts src/views/component-build/__tests__/yaml-working-document.test.ts src/views/component-build/__tests__/component-spec-field-events.test.ts
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add frontend/src/views/component-build frontend/src/service frontend/package.json pnpm-lock.yaml
git commit -m "feat: edit uploaded ComponentSpec YAML live"
```

Only stage the actual API module under `frontend/src/service`; do not stage unrelated files.

---

## Task 6: Verify end-to-end behavior with a real build

**Files:**

- No production changes expected.

**Step 1: Run backend verification**

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_component_spec_document.py backend/tests/test_component_build_api.py backend/tests/test_component_build_service.py backend/tests/test_component_spec_fusion.py -q
```

**Step 2: Run frontend verification**

```powershell
pnpm exec tsx --test src/views/component-build/__tests__/component-spec-loader.test.ts src/views/component-build/__tests__/yaml-working-document.test.ts src/views/component-build/__tests__/component-spec-field-events.test.ts
pnpm build
```

Run the targeted `vue-tsc` configuration again and delete it afterward.

**Step 3: Exercise the live API**

Using the running backend on port 5180 and a real `flange-001` build:

- GET its current ComponentSpec;
- PUT a YAML document containing a comment and an unknown nested field;
- GET it again and verify exact YAML/filename recovery;
- submit a mismatching YAML/data pair and verify HTTP 422;
- restore the original document if the live record was mutated for verification.

**Step 4: Exercise the browser UI**

Open the existing component-build page:

- upload a `.yaml` or `.yml` file;
- verify fields appear on the left;
- edit `identity.name`;
- verify the current YAML preview changes instantly;
- save, close, reopen, and verify values, comments, order, filename, and unknown fields persist.

If browser control is unavailable, report that limitation explicitly and provide the API/build evidence instead.

**Step 5: Review scope and history**

Run:

```powershell
git status --short
git diff --check
git log --oneline -8
```

Do not push until the user explicitly asks after reviewing the verified result.
