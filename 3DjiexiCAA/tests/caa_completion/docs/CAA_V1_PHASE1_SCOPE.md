# CAA V1 Phase 1 Scope

This document freezes the CAA V1 Phase 1 acceptance boundary for CATIA V5R21 x86 parser work. It is intentionally narrower than the full completion contract in `tests/caa_completion/spec/completion_contract.json`.

## Accepted Phase 1 Capabilities

- CATPart and CATProduct document identification.
- CATProduct Product/Component hierarchy traversal with stable instance paths.
- Absolute CATProduct instance transform extraction.
- PRODUCT-01 and PRODUCT-02 local-point to world-point numeric validation.
- Native `startup_type` recognition and canonical type classification, reported separately as `native_feature_type_extraction`.
- Implemented Hole, Pad, Pocket, constant Edge Fillet and Boolean operation payload extraction through R21 Public CAA interfaces, reported separately from type recognition as `native_feature_parameter_extraction`.
- Phase 1 payload acceptance is field-level, not count-only: each in-scope family must satisfy `native_feature_parameter_field_contract` in `tests/caa_completion/contracts/caa_v1_phase1_contract.json`, including required fields, field status, source API, units or normalized values, and reference counts where applicable.
- Shell and Thickness have real decoder branches and real-run evidence, but are not yet part of the Phase 1 required fixture list until their field contract and fixture matrix are promoted together.
- B-Rep topology body/cell/wire/coedge output from current R21 Public APIs. `final_brep_topology_extraction` is complete only when Loop/Coedge-level references are present, coedge previous/next links close inside the owning wire, Face-Edge and Edge-Face reverse links are present, and Face-Face adjacency is symmetric.
- Current exact face/edge geometry evidence for parsed analytic solids. `final_brep_geometry_extraction` is complete only when exact curve/surface types, non-empty geometry parameters, CATSurface/CATCurve parameter domains, and non-unknown material side for faces are emitted; center/area/length alone is partial geometry evidence. NURBS control point/knot/weight extraction is implemented against R21 Public `CATNurbsSurface`, `CATNurbsCurve` and `CATKnotVector`, but remains `not_available` on fixtures that contain no main-solid NURBS topology.
- Current mesh-to-B-Rep face range evidence where tessellation succeeds. `mesh_brep_face_mapping` is complete only when every renderable Face has a successful unique triangle range.
- ResultOUT cell to final solid cell runtime survival evidence, reported only as `runtime_cell_identity` / `survives_to_final`.
- Consistent capability states, counts and coverage definitions across `capabilities.json` and `capability_matrix.json`.

## Explicit Non-Claims

- Persistent Feature-Topology history mapping is not complete in Phase 1.
- `generated`, `modified`, `consumed`, `split` and `merged` relation semantics are not claimed from runtime pointer identity.
- Cross-session persistent naming is not claimed.
- Complete forward and reverse historical mapping is not claimed.
- Feature families with missing field-level contract coverage or incomplete formal V5R21 sample coverage remain outside the accepted claim until real samples are parsed and validated: Chamfer, Draft, Shell/Thickness promotion, Shaft, Groove, Rib, Slot, Rectangular/Circular/User Pattern, variable Fillet, face Fillet and tritangent Fillet. They must not be counted as Phase 1 complete from source code or payload row counts alone.
- Complete FTA-to-Topology mapping is not included.
- Full trimmed UV-loop semantics, curvature fields and cross-session persistent topology names are not included. Raw CATSurface/CATCurve parameter domains and CATSide material-side evidence are included only where emitted by R21 Public APIs and validated by the scoped fixtures.

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

## Anti-Forgery Gates

The validator rejects the following false-complete patterns:

- `native_feature_parameter_extraction=complete` while any native feature row is only `type_only`, has no payload type, lacks `payload_extraction_status=complete`, or fails the field-level payload contract for the fixture's expected families.
- `final_brep_topology_extraction=complete` while any referenced topology ID is dangling, a Face has no Loop/Wire, a Wire has no valid Edge, a Wire is not closed by Edge-Vertex continuity, coedge ring links are missing, reverse Face-Edge links are missing, Face-Face adjacency is asymmetric, or `coedge_count=0`.
- `final_brep_geometry_extraction=complete` while Face/Edge rows use empty `geometry_parameters`, generic geometry labels such as `success`, missing parameter domains, or unknown face material side.
- `mesh_brep_face_mapping=complete` while any renderable Face is unmapped, any mesh row references a missing Face, or any mapped range has zero triangles or failed tessellation.
