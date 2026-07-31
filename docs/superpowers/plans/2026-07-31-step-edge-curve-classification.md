# STEP Edge Curve Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace heuristic STEP edge classification with deterministic FreeCAD `TypeId` dispatch, complete curve parameters, and first-class degenerate-edge handling.

**Architecture:** Keep curve extraction inside `backend/freecad_scripts/parse_step.py`, but split it into small helpers for safe attribute access, shared edge metadata, exact 3D/2D type maps, analytic curve serialization, and degenerate p-curves. The checked-in parser remains the source of truth; the active `D:\cad-service\scripts\parse_step.py` receives the same parser implementation for live verification.

**Tech Stack:** Python 3.11 from `D:\anaconda\envs\3dcad`, FreeCAD 1.1/OpenCASCADE, pytest, FastAPI backend.

## Global Constraints

- Type dispatch uses exact FreeCAD `TypeId` values only.
- Cover line, circle, ellipse, hyperbola, parabola, Bezier, B-Spline, offset, other, invalid, and degenerate edges.
- Preserve parameter range, endpoints, closed/periodic/trimmed flags, and type-specific parameters.
- A valid degenerate edge is not an error and stores every available 2D p-curve.
- A single unextractable edge must not abort the entire STEP parse.
- Use `D:\anaconda\envs\3dcad\python.exe` for Python tests and backend calls.

---

### Task 1: Exact 3D curve dispatch and serialization

**Files:**
- Modify: `backend/tests/test_parse_step_v2.py`
- Modify: `backend/freecad_scripts/parse_step.py`

**Interfaces:**
- Consumes: FreeCAD edge objects exposing `Curve`, `FirstParameter`, `LastParameter`, and `valueAt`.
- Produces: `edge_geometry(edge) -> tuple[str, dict]`.

- [ ] **Step 1: Write failing parameterized tests**

Add fake curve objects whose exact `TypeId` values cover:

```python
[
    ("Part::GeomLine", "line"),
    ("Part::GeomCircle", "circle"),
    ("Part::GeomEllipse", "ellipse"),
    ("Part::GeomHyperbola", "hyperbola"),
    ("Part::GeomParabola", "parabola"),
    ("Part::GeomBezierCurve", "bezier_curve"),
    ("Part::GeomBSplineCurve", "bspline_curve"),
    ("Part::GeomOffsetCurve", "offset_curve"),
]
```

Assert exact type dispatch plus representative fields: line direction; circle radius; ellipse radii; hyperbola focal length; parabola focal length; Bezier poles/weights; B-Spline degree/knots/multiplicities; offset value and recursively serialized basis curve. Add a separate test proving an unlisted valid `TypeId` becomes `other_curve` with that exact ID and sampled points.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_parse_step_v2.py -q
```

Expected: new assertions fail because the current implementation uses class-name substring matching and omits the requested fields.

- [ ] **Step 3: Implement exact maps and safe serializers**

Add:

```python
CURVE_TYPE_IDS = {
    "Part::GeomLine": "line",
    "Part::GeomCircle": "circle",
    "Part::GeomEllipse": "ellipse",
    "Part::GeomHyperbola": "hyperbola",
    "Part::GeomParabola": "parabola",
    "Part::GeomBezierCurve": "bezier_curve",
    "Part::GeomBSplineCurve": "bspline_curve",
    "Part::GeomOffsetCurve": "offset_curve",
}
```

Implement safe scalar/vector/list/call helpers and a serializer per curve type. Include `curve_type_id`, parameter range, start/end point, closed, periodic, and trimmed in the common geometry. Use edge sampling only for `other_curve`; never replace a known analytic type with sampled or NURBS output.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 1 tests with the same pytest command and confirm zero failures.

### Task 2: Degenerate edges and 2D p-curves

**Files:**
- Modify: `backend/tests/test_parse_step_v2.py`
- Modify: `backend/freecad_scripts/parse_step.py`

**Interfaces:**
- Consumes: an edge for which `edge.Curve` raises, plus `Length`, `Vertexes`, `ParameterRange`, `valueAt`, and `curveOnSurface(index)`.
- Produces: `("degenerate_edge", {"point": ..., "parameter_range": ..., "pcurves": [...]})`.

- [ ] **Step 1: Replace the old unknown-curve test with failing degenerate tests**

Give `UndefinedCurveEdge` a near-zero length, one vertex, parameter range, stable `valueAt`, and a first `curveOnSurface(0)` result containing a fake `Part::Geom2dLine`. Assert:

```python
assert edge["geometry_type"] == "degenerate_edge"
assert edge["geometry"]["point"] == [0.0, 0.0, 0.0]
assert edge["geometry"]["pcurves"][0]["geometry_type"] == "line_2d"
assert edge["geometry"]["pcurves"][0]["surface_type_id"] == "Part::GeomSphere"
```

Add a non-degenerate failure case and assert `invalid_curve` with its structured error.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_parse_step_v2.py -q
```

Expected: current `unknown_curve` behavior fails the new assertions.

- [ ] **Step 3: Implement degenerate detection and p-curve extraction**

Use both topology and tolerance:

```python
length <= max(1e-12, edge_tolerance) and len(edge.Vertexes) <= 1
```

Map exact 2D IDs to `line_2d`, `circle_2d`, `ellipse_2d`, `hyperbola_2d`, `parabola_2d`, `bezier_curve_2d`, `bspline_curve_2d`, `offset_curve_2d`; otherwise retain `other_curve_2d` and its exact `TypeId`. Iterate `curveOnSurface(index)` until it returns `None`.

- [ ] **Step 4: Run parser tests and verify GREEN**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_parse_step_v2.py backend/tests/test_parser_runner.py -q
```

Expected: all parser tests pass.

### Task 3: Live parser synchronization and real-model regression

**Files:**
- Modify: `D:\cad-service\scripts\parse_step.py`
- Delete after use: `backend/freecad_scripts/diagnose_edge_curves.py`

**Interfaces:**
- Consumes: checked-in parser behavior from Tasks 1–2.
- Produces: a live `result.json` and completed database revision.

- [ ] **Step 1: Synchronize the active parser**

Apply the same curve helpers and `edge_geometry` implementation to `D:\cad-service\scripts\parse_step.py`. Preserve runtime-specific schema and unrelated parsing behavior.

- [ ] **Step 2: Run the real STEP through FreeCAD**

Execute `D:\anaconda\envs\3dcad\Library\bin\freecadcmd.exe` with:

```text
D:\cad-work\5bd7d8a5-2e0f-4abb-aafd-53ca4e3d15a0\job.json
```

and the active parser. Require exit code `0` and a newly written `result.json`.

- [ ] **Step 3: Verify the real edge inventory**

Parse `result.json` and assert:

```text
unknown_curve = 0
invalid_curve = 0
degenerate_edge = 18
every degenerate edge has line_2d p-curve metadata
```

- [ ] **Step 4: Re-ingest and verify API state**

Run `CadService.parse_revision` in the `3dcad` Python environment, then verify:

```text
GET /api/cad/revisions/5bd7d8a5-2e0f-4abb-aafd-53ca4e3d15a0/status
status = completed
progress = 100
```

### Task 4: Final verification, commit, and direct push

**Files:**
- Commit only: curve parser, parser tests, runner diagnostic improvement, design, and this plan.
- Exclude: unrelated dirty frontend/backend files and generated CAD artifacts.

- [ ] **Step 1: Run fresh verification**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_parse_step_v2.py backend/tests/test_parser_runner.py -q
git diff --check
```

- [ ] **Step 2: Inspect scoped diff**

Confirm the commit contains only:

```text
backend/freecad_scripts/parse_step.py
backend/tests/test_parse_step_v2.py
backend/app/cad/parser_runner.py
backend/tests/test_parser_runner.py
docs/superpowers/specs/2026-07-31-step-edge-curve-classification-design.md
docs/superpowers/plans/2026-07-31-step-edge-curve-classification.md
```

- [ ] **Step 3: Commit**

Create a focused commit such as:

```text
fix: classify all STEP edge curve types
```

- [ ] **Step 4: Update and push main safely**

Fetch `origin/main`. If the remote advanced, integrate it without overwriting local or user changes; rerun tests after integration. Then push the current `main` to `origin/main` without force.
