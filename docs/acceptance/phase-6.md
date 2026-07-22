# Phase 6 Acceptance

## Scope

Implemented rule/config foundations only:

- `format-only.yaml` defines output hierarchy only.
- `component-spec.schema.json` defines structural validation shape.
- `field-catalog.yaml` defines field semantics, aliases, units, sources, and applicable component types.
- `profiles/generic.yaml` is the fallback profile.
- `profiles/flange-weld-neck-hgt20592.yaml` contains the weld-neck flange mappings.

No AI, LLM, automatic semantic inference, final YAML export, or PASS/FAIL UI was added.

## Profile Behavior

The flange profile defines these mappings:

```text
D  -> flange_outer_diameter
K  -> bolt_circle_diameter
n  -> bolt_hole_count
L  -> bolt_hole_diameter
C  -> flange_thickness
H  -> overall_height
R  -> root_fillet_radius
f1 -> raised_face_height
A1 -> pipe_outer_diameter
N  -> hub_small_end_diameter
```

`H1` is not mapped directly. It is emitted as `drawing_parameter_H1` with ambiguity metadata and `needs_review=true`.

`d` is defined only in the flange profile as `flange_bore_diameter`, with `require_semantic_confirmation=true` and `needs_review=true`. Generic code does not recognize `d` as bore.

Generic profile behavior:

- Unknown components do not fail.
- Drawing symbols are preserved.
- Parameters are emitted as `drawing_parameter_<symbol>`.
- All generic parameters are marked `needs_review=true`.
- No `flange_*` fields are emitted.

## Template Safety

`structure_only` mode strips unverified example values from uploaded templates and keeps only parameter names. `field-template` mode fills parameters by `name`, not by array index.

## Verification

Command:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_spec_profiles_phase6.py -q
```

Actual output:

```text
6 passed in 0.50s
```

Full backend regression command:

```powershell
cd backend
D:\anaconda\envs\3dcad\python.exe -m pytest -q
```

Actual output summary:

```text
84 passed, 6 failed, 1 warning in 25.82s
```

Failed items:

```text
tests/test_measurement_xms06_acceptance.py::test_xms06_measurement_acceptance_values_and_sources
tests/test_measurement_xms06_acceptance.py::test_measurement_repository_rerun_is_idempotent_for_counts_and_uuids
tests/test_xms06_phase1_acceptance.py::test_xms06_counts_match_revision_entities_meshes_and_golden_fixture
tests/test_xms06_phase1_acceptance.py::test_xms06_persisted_revision_face_count_matches_face_entities_and_meshes
tests/test_xms06_phase1_acceptance.py::test_xms06_topology_relations_are_complete_and_reference_existing_entities
tests/test_xms06_phase1_acceptance.py::test_xms06_same_revision_rerun_keeps_topology_uuids_and_relation_counts_stable
```

Known failure reason observed in all six failed tests:

```text
FreeCAD parser failed with exit code 3221225781; stdout=; stderr=
```

## Known Limits

- This phase does not persist ComponentSpec drafts to PostgreSQL and does not expose an API.
- This phase does not export final YAML.
- Profile matching is rule-based and intentionally conservative; ambiguous mappings remain review candidates.
