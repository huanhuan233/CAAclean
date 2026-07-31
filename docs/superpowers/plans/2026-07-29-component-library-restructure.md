# 图元库存储管理页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the existing component-build page from a file-tree + right-side detail workbench into a left-catalog + right-table + edit-dialog component library management layout, preserving all existing business logic.

**Architecture:** Single-page SFC split into focused sub-components under `modules/`. The main `index.vue` orchestrates state, data loading, and routing; child components receive props and emit events. A separate `mock/library-ui.ts` file holds UI-only demo data (call volume, YAML local storage). The 3-tab edit dialog replaces the current ElDrawer as the primary editing interface.

**Tech Stack:** Vue 3 + TypeScript + Element Plus + Soybean Admin (iconify icons via `icon-*` components) + `--el-color-primary` as the theme color.

## Global Constraints

- NO backend modifications (no new API routes, no db changes)
- NO modifications to frontend/src/views/cad-model/, cad-spec/, patent-annotation/
- NO changes to global theme or common layout
- All existing business functions must remain callable: createComponentBuild, updateComponentBuild, fetchComponentBuildTree, fetchComponentBuildCatalog, fetchComponentBuild, fetchComponentBuildStatus, retryComponentBuild, fetchComponentSpec, saveComponentSpec, previewComponentSpec, fuseComponentBuild
- NO React or static data replacing real API calls
- Mock data must be clearly labeled as UI demo with `[UI_DEMO]` comments
- TypeScript no large `any` areas
- Polling timer cleared on component unmount
- FileReader error handling required
- Object URLs must be released

---

## File Structure

```
frontend/src/views/component-build/
├── index.vue                     # [MODIFY] Main orchestrator — new layout using sub-components
├── component-spec-v1.2.json      # unchanged
├── modules/
│   ├── ComponentSpecFieldEditor.vue   # unchanged (existing)
│   ├── ComponentLibraryCatalog.vue    # [CREATE] Left catalog panel
│   ├── ComponentLibraryTable.vue      # [CREATE] Right table with search
│   ├── ComponentLibraryDialog.vue     # [CREATE] 3-tab edit/create dialog
│   └── ComponentYamlPreview.vue       # [CREATE] YAML preview with field editor split
└── mock/
    └── library-ui.ts              # [CREATE] UI demo mock data (call volume, YAML local storage)
```

## Key Interfaces

```typescript
// Types shared across sub-components (derived from existing API types)

/** A flattened row representing one build in the table. */
interface BuildTableRow {
  id: string                    // build_id
  component_id: string
  component_name: string
  category_code: string | null
  part_type_code: string | null
  standard_number: string | null
  version: string | null
  status: string
  family: string | null          // catalog label
  component_type: string | null  // part type label
  cad_revision_id: string | null
  drawing_task_id: string | null
  hasStep: boolean
  hasDrawing: boolean
  // enriched at display time:
  default_dn?: string
  default_pn?: string
}

/** Catalog item for the left panel */
interface CatalogTreeItem {
  id: string                     // category_code or '__root__'
  label: string
  code: string
  count: number                  // number of builds under this category
}
```

---
