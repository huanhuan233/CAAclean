# CAA V1 Phase 1 Scope

This document freezes the CAA V1 Phase 1 acceptance boundary for CATIA V5R21 x86 parser work. It is intentionally narrower than the full completion contract in `tests/caa_completion/spec/completion_contract.json`.

## Accepted Phase 1 Capabilities

- CATPart and CATProduct document identification.
- CATProduct Product/Component hierarchy traversal with stable instance paths.
- Absolute CATProduct instance transform extraction.
- PRODUCT-01 and PRODUCT-02 local-point to world-point numeric validation.
- Native `startup_type` recognition and canonical type classification.
- Implemented Hole, Pad and Pocket parameter payload extraction through R21 Public CAA interfaces.
- Basic B-Rep topology body/cell/wire output from current R21 Public APIs.
- Current mesh-to-B-Rep face range evidence where tessellation succeeds.
- ResultOUT cell to final solid cell runtime survival evidence, reported only as `runtime_cell_identity` / `survives_to_final`.
- Consistent capability states, counts and coverage definitions across `capabilities.json` and `capability_matrix.json`.

## Explicit Non-Claims

- Persistent Feature-Topology history mapping is not complete in Phase 1.
- `generated`, `modified`, `consumed`, `split` and `merged` relation semantics are not claimed from runtime pointer identity.
- Cross-session persistent naming is not claimed.
- Complete forward and reverse historical mapping is not claimed.
- Fillet, Chamfer, Pattern, Boolean and GSD parameter decoders remain type-only or partial unless a dedicated Public CAA decoder has read payload values.
- Complete FTA-to-Topology mapping is not included.
- Full surface parameters, UV domains, material side, curvature and complete geometry semantics are not included.

## Coverage Definitions

For `native_feature_topology_mapping`, `coverage_ratio` is retained for schema compatibility and means `authoritative_coverage_ratio`.

`runtime_coverage_ratio` is:

```text
(runtime_identity_count + authoritative_history_count) / required_count
```

`authoritative_coverage_ratio` is:

```text
authoritative_history_count / required_count
```

Runtime identity alone can prove only that a ResultOUT cell object survived into the final runtime solid enumeration in the same process. It cannot prove creation history, modification history, consumption, split, merge, or cross-session identity. Therefore runtime identity can never make `native_feature_topology_mapping` complete.

## Product Capability Definitions

`product_structure_extraction=complete` requires every non-root CATProduct instance to have a unique instance path, resolved parent-child closure, a reference product identity, no duplicate paths, and no unresolved nodes.

`instance_transform_extraction=complete` requires every non-root instance to have one finite 4x4 absolute transform, a valid homogeneous last row, an orthogonal rotation submatrix, determinant near `+1`, a one-to-one instance path to matrix association, and successful PRODUCT-01/02 numeric truth validation when those fixtures are in scope.

For CATPart documents both Product capabilities are `not_applicable`. For root-only CATProduct documents, Product structure can be complete while instance transform extraction is `not_applicable`.

## Full Contract Status

Phase 1 PASS must not be described as full CAA completion. The full completion contract continues to require authoritative persistent Feature-Topology history, full relation semantics, complete FTA mapping, and broader decoder coverage. Those items remain `partial`, `not_available`, `not_implemented`, or `blocked_public_api_r21` until proven by code and real CATIA V5R21 evidence.
