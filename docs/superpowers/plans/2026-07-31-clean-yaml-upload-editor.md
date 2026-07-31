# Clean YAML Upload Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make unsaved ComponentSpec editors empty until a YAML file is uploaded, then render dynamic fields on the left and the live YAML on the right.

**Architecture:** Keep the existing YAML AST working document, but only construct it for persisted documents or successful uploads. Replace the system-template preview with a single current-document preview whose upload control is always available.

**Tech Stack:** Vue 3, TypeScript, Element Plus, yaml 2.8.3, Node 20.20.2.

## Global Constraints

- Work directly on `main`.
- Do not show template fields or template YAML for `saved: false`.
- Persist and reopen uploaded `data`, `yaml`, and `source_filename`.
- Preserve YAML parse errors without replacing the current document.

---

### Task 1: Empty-state decision

**Files:**
- Modify: `frontend/src/views/component-build/component-spec-editor-state.ts`
- Test: `frontend/src/views/component-build/__tests__/component-spec-loader.test.ts`

**Interfaces:**
- Consumes: `ComponentSpecDocumentLike.saved`
- Produces: `createPersistedComponentSpecEditorState(document): ComponentSpecEditorState | null`

- [ ] Add a failing test asserting unsaved documents return `null` while saved YAML documents create state.
- [ ] Run the focused test and confirm the unsaved case fails.
- [ ] Implement the persisted-document gate without generating fallback YAML.
- [ ] Run the focused test and confirm it passes.

### Task 2: Upload-only preview

**Files:**
- Modify: `frontend/src/views/component-build/modules/ComponentYamlPreview.vue`
- Modify: `frontend/src/views/component-build/modules/ComponentLibraryDialog.vue`
- Test: `frontend/src/views/component-build/__tests__/component-spec-loader.test.ts`

**Interfaces:**
- Consumes: nullable editor state and uploaded YAML text
- Produces: always-visible `uploadYaml` action, single current YAML preview, dynamic field state after upload

- [ ] Add a failing state-transition test proving YAML upload can create the first editor document without a template state.
- [ ] Run the focused test and confirm the new function is missing.
- [ ] Add `createComponentSpecEditorStateFromUpload(yaml, filename, sections)` and use it when no editor exists.
- [ ] Remove system/current tabs and restore-system behavior from the preview and dialog.
- [ ] Keep the left empty state until upload succeeds.
- [ ] Run focused tests and confirm they pass.

### Task 3: Remove frontend template fallback

**Files:**
- Modify: `frontend/src/views/component-build/index.vue`
- Modify: `frontend/src/views/component-build/modules/ComponentLibraryDialog.vue`

**Interfaces:**
- Consumes: backend `saved` flag and optional browser draft
- Produces: no editor for a new server document; restored editor for saved server YAML

- [ ] Stop creating a `component-spec-v1.2.json` document for new builds.
- [ ] Pass unsaved server responses to the dialog as empty state.
- [ ] Keep real offline uploaded drafts recoverable.
- [ ] Disable save and fusion until an editor document exists.

### Task 4: Verification and delivery

**Files:**
- Verify all files above.

- [ ] Run all component-build frontend tests with Node 20.20.2.
- [ ] Run `pnpm typecheck`.
- [ ] Run `pnpm build`.
- [ ] Run `git diff --check`.
- [ ] Commit implementation on `main`.
- [ ] Push `main` and verify the live Vite module serves the upload-only UI.
