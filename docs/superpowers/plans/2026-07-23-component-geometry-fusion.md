# Component Geometry Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate ComponentSpec coordinate, geometry recipe, output, and validation fields from STEP feature candidates and flange rules.

**Architecture:** Extend the existing deterministic fusion module with a focused geometry-fusion helper. It consumes normalized `main_axis_candidate` and `circular_pattern` records already loaded by `SqlAlchemyFusionSourceReader`, writes only existing v1.2 template paths, and uses the current fill-empty/overwrite policy.

**Tech Stack:** Python 3.12, dataclasses, pytest, FastAPI/SQLAlchemy integration already present in the repository.

## Global Constraints

- Preserve user-entered values during default fusion.
- Do not invent generator files, engine versions, people, dates, or hashes.
- Mark semantic coordinate descriptions as needing review.
- Preserve the unrelated `frontend/src/locales/langs/zh-cn.ts` worktree change.

---

### Task 1: Coordinate and Geometry Fusion Rules

**Files:**
- Modify: `backend/tests/test_component_spec_fusion.py`
- Modify: `backend/app/component_builds/fusion.py`

**Interfaces:**
- Consumes: `FusionSources.features`, flange parameters already inserted into the draft.
- Produces: populated `coordinate_system`, `geometry`, and `validation` template sections.

- [ ] **Step 1: Write failing behavior tests**

Add assertions that a high-confidence main-axis and circular-pattern source produces:

```python
assert result.data["coordinate_system"]["origin"] == [0.0, -50.0, 0.0]
assert result.data["coordinate_system"]["z_axis"] == [0.0, 1.0, 0.0]
assert result.data["geometry"]["representation"] == "parametric_recipe"
assert result.data["geometry"]["construction"][1]["operation"] == "polar_pattern_cut"
assert result.data["validation"]["geometry"]["bounding_box_expression"]["x_size"] == "flange_outer_diameter"
```

Add a fallback test proving an axis without a circular pattern still creates an orthonormal local frame and does not invent a bolt-hole operation.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend\tests\test_component_spec_fusion.py -q -p no:cacheprovider
```

Expected: assertions fail because coordinate and geometry fields are empty.

- [ ] **Step 3: Implement the minimal geometry helper**

Add `_fuse_geometry(...)` and small vector helpers in `fusion.py`. Select the highest-confidence main axis and circular pattern, normalize a local frame, write flange construction operations, export defaults, and validation defaults through the existing `assign` callback.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the command from Step 2. Expected: all tests pass.

### Task 2: Real XMS06-DN80 Verification

**Files:**
- Modify only if a real-data mismatch exposes a tested defect:
  - `backend/app/component_builds/fusion.py`
  - `backend/tests/test_component_spec_fusion.py`

**Interfaces:**
- Consumes: build `14f8e7e9-d940-4625-a89f-9c85791e003d`.
- Produces: persisted ComponentSpec draft populated through the existing fusion API.

- [ ] **Step 1: Run backend regressions**

Run the component-build, fusion, catalog, and parser-runner test set with a project-local pytest temporary directory.

- [ ] **Step 2: Start the backend in conda environment `3dcad`**

Run Uvicorn with `D:\anaconda\envs\3dcad\python.exe` on an unused local port.

- [ ] **Step 3: Execute overwrite fusion for XMS06-DN80**

POST:

```json
{"overwrite": true}
```

to `/api/component-builds/14f8e7e9-d940-4625-a89f-9c85791e003d/fusion`.

- [ ] **Step 4: Verify persisted values**

Confirm coordinate axes, semantic definitions, geometry construction, STEP output, and validation values through the component-spec API and the existing browser page.

- [ ] **Step 5: Verify frontend and commit**

Run Vue type checking and the production Vite build. Commit only the design, plan, fusion implementation, and tests; do not stage the unrelated locale change.
