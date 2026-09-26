# Progressive Native Tree Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the CAA native tree as soon as worker capture completes while Feature Center and GLB generation continue in the background.

**Architecture:** Publish native bundle metadata at the ingest boundary immediately after worker extraction. Let the viewer service expose that metadata during processing, then make the frontend hydrate the tree before the ready-state gate and poll until geometry becomes available.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async repositories, Vue 3, TypeScript, Vitest, pytest.

## Global Constraints

- Keep the revision in `processing` until the existing Feature Center validation succeeds.
- Do not expose a `viewer_asset` before every required GLB-side asset exists.
- Preserve the native tree if Feature Center later fails.
- Do not modify or discard unrelated uncommitted user changes.

---

### Task 1: Publish Native Assets Before Feature Center

**Files:**
- Modify: `backend/app/component_builds/ingest.py`
- Test: `backend/tests/test_part_ingest.py`

**Interfaces:**
- Consumes: extracted `native_bundle: Path` and `CadRepository.update_revision_manifest`.
- Produces: `async _publish_native_progress(repository, revision_id, native_bundle) -> None` and an intermediate manifest containing `native_capture`, `native_semantics`, and `viewer_summary`.

- [ ] **Step 1: Write the failing test**

Add a repository fake that records manifest updates and a blocked Feature Center command. Assert that `_run_catpart_route` publishes `native_semantics.available == True` and a tree path before the blocked command completes.

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_part_ingest.py -k native_progress -q`

Expected: FAIL because native semantics are only published after Feature Center completion.

- [ ] **Step 3: Write minimal implementation**

Extract the native-only manifest construction into `_native_progress_manifest(native_bundle)` and call it immediately after local capture or remote worker extraction, before setting `feature_center_processing`.

- [ ] **Step 4: Run test to verify it passes**

Run the same focused pytest command. Expected: PASS.

### Task 2: Return a Progressive Viewer Contract

**Files:**
- Modify: `backend/app/component_builds/service.py`
- Test: `backend/tests/test_component_build_service.py`

**Interfaces:**
- Consumes: intermediate native metadata from Task 1.
- Produces: a processing `ViewerContract` with native URLs and `viewer_asset: null`.

- [ ] **Step 1: Write the failing test**

Create a processing revision with an available native bundle. Assert that `get_viewer_contract` returns `status == "processing"`, `native_capture.has_tree == True`, usable `native_semantics.tree_occurrences_url`, and no viewer asset. Also assert `get_native_tree` reads it.

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_component_build_service.py -k progressive_native -q`

Expected: FAIL until the intermediate manifest is recognized consistently.

- [ ] **Step 3: Write minimal implementation**

Keep the existing processing branch, but ensure it returns the progressive native contracts from the intermediate manifest and allows `_native_bundle_reader` whenever `native_semantics.available` is true.

- [ ] **Step 4: Run test to verify it passes**

Run the same focused pytest command. Expected: PASS.

### Task 3: Hydrate Tree Before Geometry Is Ready

**Files:**
- Modify: `frontend/src/views/feature-center/index.vue`
- Test: `frontend/src/views/feature-center/__tests__/viewer-workspace.test.ts`

**Interfaces:**
- Consumes: progressive `ViewerContract` from Task 2 and `loadOptionalSemanticAssets`.
- Produces: visible left tree during processing plus continued polling for GLB assets.

- [ ] **Step 1: Write the failing test**

Mount the workspace with a processing contract that has `native_capture.has_tree`. Assert that the native tree request runs before a ready contract is returned and that another contract poll is scheduled.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend vitest run src/views/feature-center/__tests__/viewer-workspace.test.ts`

Expected: FAIL because `loadBuildBundle` returns before semantic assets are loaded.

- [ ] **Step 3: Write minimal implementation**

In `loadBuildBundle`, load optional native semantic assets whenever the processing contract advertises a tree, then schedule the next status poll. Preserve already loaded tree state when the ready contract arrives and load the viewer asset separately.

- [ ] **Step 4: Run test to verify it passes**

Run the same Vitest command. Expected: PASS.

### Task 4: Regression and Live Verification

**Files:**
- Verify only; no production changes.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: test and live API evidence.

- [ ] **Step 1: Run backend regression tests**

Run: `D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_part_ingest.py backend/tests/test_component_build_service.py backend/tests/test_component_build_api.py -q`

- [ ] **Step 2: Run frontend regression tests**

Run: `pnpm --dir frontend vitest run src/views/feature-center/__tests__/viewer-workspace.test.ts src/views/feature-center/__tests__/native-feature-tree.test.ts`

- [ ] **Step 3: Verify the live processing contract**

Fetch `/api/component-builds/{build_id}/viewer` while `current_stage` is `feature_center_processing`; verify native tree availability and `viewer_asset == null`, then verify viewer assets appear after completion.

- [ ] **Step 4: Check the patch**

Run: `git diff --check`

Expected: no whitespace errors. Leave overlapping user changes uncommitted rather than claiming ownership of them.
