# Phase 2 Acceptance

Date: 2026-07-22

## Scope

Implemented generic geometry post-processing on top of Phase 1's persisted unique Face, Edge, and Vertex entities.

Implemented:

- New PostgreSQL-backed ORM tables:
  - `cad_feature_candidates`
  - `cad_measurements`
- Independent `app.measurement` modules:
  - `axis_detector.py`
  - `envelope.py`
  - `analytic_groups.py`
  - `plane_groups.py`
  - `hole_detector.py`
  - `circular_patterns.py`
  - `fact_builder.py`
  - `repository.py`
  - `service.py`
  - `schemas.py`
- Generic feature candidates:
  - `main_axis_candidate`
  - `cylindrical_hole_candidate`
  - `through_hole_candidate`
  - `blind_hole_candidate`
  - `circular_pattern`
- Generic measurements:
  - `bounding_box_x`
  - `bounding_box_y`
  - `bounding_box_z`
  - `overall_length_along_main_axis`
  - `maximum_radial_diameter`
  - `cylinder_diameter`
  - `circle_diameter`
  - `parallel_plane_distance`
  - `fillet_radius_candidate`
  - `cone_angle_candidate`
- Idempotent replacement per `revision_id` plus `algorithm_version`; a new algorithm version records new rows instead of silently overwriting older-version rows.
- XMS06-DN80 deterministic acceptance facts:
  - highest-confidence `main_axis_candidate` count: 1
  - main-axis confidence: at least `0.90`
  - `maximum_radial_diameter`: `200 +/- 0.1 mm`
  - `overall_length_along_main_axis`: `50 +/- 0.1 mm`
  - circular hole pattern count: `8`
  - member diameter: `18 +/- 0.1 mm`
  - pitch circle diameter: `160 +/- 0.1 mm`
  - angular spacing: `45 +/- 0.1 deg`

Not implemented in this phase:

- VLM
- LLM
- YAML
- Domain-specific field mapping
- ComponentSpec page

## Commands And Actual Output

### Focused Phase 2 Tests

Command:

```powershell
conda run -n 3dcad pytest backend/tests/test_measurement_models.py backend/tests/test_measurement_algorithms.py backend/tests/test_measurement_repository.py -q
```

Output:

```text
.........                                                                [100%]
9 passed in 2.28s
```

### XMS06 Deterministic Measurement Acceptance

Command:

```powershell
conda run -n 3dcad pytest backend/tests/test_measurement_xms06_acceptance.py -q
```

Output:

```text
...                                                                      [100%]
3 passed in 17.85s
```

This verifies:

- Exactly one highest-confidence main-axis candidate.
- Main-axis confidence is at least `0.90`.
- Maximum radial diameter is `200 +/- 0.1 mm`.
- Main-axis total length is `50 +/- 0.1 mm`.
- Circular hole pattern has `8` members.
- Member diameter is `18 +/- 0.1 mm`.
- Pitch circle diameter is `160 +/- 0.1 mm`.
- Angular spacing is `45 +/- 0.1 deg`.
- Every measurement has `method`, `algorithm_version`, non-empty valid `source_entity_ids`, explicit `unit`, and distinct raw / normalized value containers.
- Negative cases do not produce circular patterns for a pure box, a single cylinder, or two random holes.
- Re-running replacement for the same revision and algorithm version keeps feature and measurement counts and UUIDs stable.

### Forbidden Domain Semantics Scan

Command:

```powershell
rg "flange_outer_diameter|bolt_hole|gear_module|bearing_outer_diameter|VLM|LLM|YAML|ComponentSpec" backend\app backend\tests
```

Output:

```text
backend\tests\test_measurement_algorithms.py:        "flange_outer_diameter",
backend\tests\test_measurement_algorithms.py:        "bolt_hole",
backend\tests\test_measurement_algorithms.py:        "gear_module",
backend\tests\test_measurement_algorithms.py:        "bearing_outer_diameter",
```

The matches are only the negative assertion list in tests. Production code does not emit these names.

### Full Backend Regression

Command:

```powershell
cd backend
conda run -n 3dcad pytest -q
```

Output:

```text
.............................................                            [100%]
============================== warnings summary ===============================
..\..\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1
  D:\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
45 passed, 1 warning in 10.40s
```

## Known Limitations

- The algorithms are generic candidates, not confirmed engineering semantics.
- Main-axis detection prioritizes analytic cylinder/cone/torus axes and falls back to the longest bounding-box span when analytic support is absent.
- Circular pattern fitting currently groups same-radius circle edges around a common axis and reports residual from angular spacing.
- No API endpoint or frontend page was added in this phase.
- The full backend suite still emits the existing FastAPI/Starlette TestClient deprecation warning.
