# CAA V1 Phase 1 V11 Acceptance Summary

Source commit: `d0d91b36cf30df6fc250c8ba399521b0fbfdcbf6`

Binary SHA-256: `9DA825E325B5A0F6106C7934666362EFD701834FDF2F16D6B1C16301C4B915C6`

## Verification

- Python validator unit tests: PASS, 27 tests.
- VS2008/C++03 core self-test: PASS.
- CATIA V5R21 32-bit `mkmk` build: PASS.
- Parser self-test under R21 environment: PASS.
- CAA V1 Phase 1 scoped suite: PASS, 7 PASS / 0 FAIL / 0 BLOCKED.
- Full completion suite: FAIL, 8 PASS / 25 FAIL / 16 BLOCKED / 3 BLOCKED_FIXTURE_R21 / 2 UNTESTED_NO_FIXTURE.

## Advanced Feature Payloads

- Fillet: complete via `CATIAConstRadEdgeFillet` on `PD-FILLET-01`.
- Chamfer: complete via `CATIAChamfer` on `PD-CHAMFER-01`.
- Shell/Thickness: complete via `CATIAShell` and `CATIAThickness` on `PD-SHELL-01`.
- Boolean Add/Remove/Assemble/Intersect: complete via `CATIABooleanShape` on `PD-BOOLEAN-01`.
- Rib/Slot: complete via `CATIASweep` on `PD-SWEEP-01`.
- Rectangular Pattern: complete via `CATIARectPattern` on `PD-PATTERN-01`.
- Shaft/Groove: partial via `CATIARevolution`; angles and thin/merge flags are read, but `get_RevoluteAxis` returns a null reference on the R21 fixture.

## Product Validation

- `PRODUCT-01`: required instances 2, resolved 2, product structure complete, absolute instance transforms complete.
- `PRODUCT-02`: required instances 4, resolved 4, product structure complete, absolute instance transforms complete.
- Validator confirmed one-to-one instance path/matrix mapping and fixture-truth absolute transforms.

## Honest Boundaries

The V1 scoped suite is green, but the full completion contract is not. The following remain deliberately partial or unavailable:

- `feature_final_topology_history=partial`
- `native_feature_topology_mapping=partial`
- `persistent_generic_naming=not_available/blocked_public_api_r21`
- `final_brep_topology_extraction=partial`
- `final_brep_geometry_extraction=partial`
- `mesh_brep_face_mapping=partial`
- `fta_topology_mapping=not_available`

These are not hidden by the V1 scoped report and remain visible in the full completion suite.
