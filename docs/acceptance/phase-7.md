# Phase 7 Acceptance

## Scope

Implemented deterministic field mapping and cross-modal evidence alignment foundations.

Inputs:

- Drawing Facts
- CAD Measurements
- Component Profile
- ComponentSpec Schema/Profile Registry

Outputs:

- In-memory `SpecFieldBinding` records
- SQLAlchemy persistence models and repository support for `cad_spec_fields` and `cad_spec_field_evidence`

No LLM or AI calls were added.

## Database

Added models:

- `CadSpecField` -> `cad_spec_fields`
- `CadSpecFieldEvidence` -> `cad_spec_field_evidence`

Each field stores:

- `drawing_value`
- `measured_value`
- `normalized_measured_value`
- `resolved_value`
- `unit`
- `drawing_fact_id`
- `measurement_id`
- `feature_id`
- `source_entity_ids`
- `mapping_status`
- `geometry_match_status`
- `conformance_status`
- `review_status`
- `drawing_value_confidence`
- `measurement_confidence`
- `mapping_confidence`
- `reason`
- `metadata`

## Status Separation

Statuses are separate:

- `mapping_status`: `matched`, `ambiguous`, `unmatched`
- `geometry_match_status`: `within_match_tolerance`, `outside_match_tolerance`, `not_measurable`
- `conformance_status`: `pass`, `fail`, `unknown`, `not_applicable`
- `review_status`: `pending`, `needs_review`, `confirmed`, `rejected`

When geometry is close but no standard tolerance is available, the mapper sets:

```text
geometry_match_status=within_match_tolerance
conformance_status=unknown
```

## Deterministic Mapping Rules

The mapper uses deterministic signals:

- Drawing symbol
- Profile field mapping
- Unit presence
- Value type
- Profile-declared `measurement_types`
- Geometry evidence
- Numerical proximity

Numerical proximity alone is not sufficient. A measurement is only aligned when its `measurement_type` is allowed by the selected Profile mapping.

STEP measured values never overwrite drawing values:

```text
resolved_value = drawing_value
```

## Comparison Semantics

Supported drawing operators:

- `eq`
- `gte`
- `lte`
- `approx`
- `between` (currently stored; not geometrically evaluated)
- `categorical`

The tests cover `eq`, `gte`, and tolerance comparison behavior. Drawing Facts remain the nominal source.

## Verification

Command:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend/tests/test_spec_bindings_phase7.py -q
```

Actual output:

```text
6 passed in 8.44s
```

## Known Limits

- No API endpoint was added in this phase.
- No UI was added in this phase.
- No final YAML export was added.
- `between` is preserved in metadata but not yet evaluated against geometry bounds.
