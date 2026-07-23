# Component Build Draft Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow component builds to be created without source files and edited later from the same drawer.

**Architecture:** Keep component metadata in `component_builds`, reuse existing CAD and drawing services when optional replacement files are supplied, and stage a drawing by build ID when no STEP revision exists yet. A multipart PATCH endpoint updates metadata and sources without clearing omitted files.

**Tech Stack:** FastAPI, SQLAlchemy async repositories, pytest, Vue 3, TypeScript, Element Plus.

## Global Constraints

- STEP and drawing are independently optional on create and edit.
- Omitted existing sources are preserved.
- A drawing uploaded before STEP is staged and processed automatically after STEP is attached.
- Component ID remains backend-generated and immutable.

---

### Task 1: Backend Draft And Edit API

**Files:**
- Modify: `backend/app/component_builds/router.py`
- Modify: `backend/app/component_builds/repository.py`
- Modify: `backend/app/component_builds/service.py`
- Test: `backend/tests/test_component_build_api.py`

**Interfaces:**
- Produces: `PATCH /api/component-builds/{build_id}` multipart endpoint.
- Produces: `ComponentBuildService.update_catalog_build(...)`.

- [ ] Add failing API tests for zero-file create, metadata-only edit, one-file create, staged drawing, and later STEP completion.
- [ ] Run focused pytest and confirm the new cases fail.
- [ ] Make POST files optional and add PATCH with optional files.
- [ ] Add repository metadata update while preserving source IDs.
- [ ] Stage pre-STEP drawings under `cad_spec_work_dir/component-build-pending/{build_id}` and consume them after STEP attachment.
- [ ] Project completed partial builds as `sources_partial` so polling terminates.
- [ ] Run focused backend tests.

### Task 2: Editable Right Drawer

**Files:**
- Modify: `frontend/src/typings/api/cad.d.ts`
- Modify: `frontend/src/service/api/cad.ts`
- Modify: `frontend/src/views/component-build/index.vue`

**Interfaces:**
- Consumes: `PATCH /api/component-builds/{build_id}`.
- Produces: one drawer with create and edit modes.

- [ ] Make both file fields optional in the payload typings and API serializer.
- [ ] Add update API serialization that only appends selected files.
- [ ] Track drawer mode and active build ID, and prefill metadata for edit.
- [ ] Add “编辑图元” on a selected build and update drawer title/button text.
- [ ] Remove file required markers and retain existing files when no replacement is selected.
- [ ] Run `corepack pnpm typecheck`.

### Task 3: Regression Verification

**Files:**
- Test: `backend/tests`
- Test: `frontend`

- [ ] Run focused component-build tests in the `3dcad` environment.
- [ ] Run frontend typecheck and test build.
- [ ] Run `git diff --check` and review the scoped diff.

### Task 4: Manual Source Parsing Controls

**Files:**
- Modify: `backend/app/component_builds/router.py`
- Modify: `backend/tests/test_component_build_api.py`
- Modify: `frontend/src/views/component-build/index.vue`

- [ ] Change STEP retry from a re-upload error into a real background parse schedule.
- [ ] Keep drawing retry connected to the existing layout and extraction pipeline.
- [ ] Add one independent “开始解析” button to each source row.
- [ ] Disable a button when its source is absent or already processing.
- [ ] Run component API tests, frontend typecheck, and test build.
