# CAA V1 Phase 1 V12 Acceptance Summary

Generated on 2026-08-05 from working tree based on source commit `865d7bf6931b33620ab518b8b3f754a237aed474`.

## Build

- Binary: `intel_a/code/bin/CadParseMvp.exe`
- Binary SHA-256: `D598F69B1D8F51BE5B011A0F59F33283F9F8B08363C850A6004BC696A4B91223`
- CATIA/CAA: V5R21 32-bit RADE/mkmk
- Compiler: Visual Studio 2008 x86, C++03
- mkmk result: PASS
- Core self-tests: PASS
- Python validator unit tests: 27 PASS

## Scoped Fixture Validation

CAA V1 Phase 1 scoped contract results for current real runs:

- `PD-PAD-01`: PASS, 1516 checks
- `PD-POCKET-01`: PASS, 1575 checks
- `PD-FILLET-01`: PASS, 1575 checks
- `PD-BOOLEAN-01`: PASS, 1751 checks
- `PRODUCT-01`: PASS, 1386 checks
- `PRODUCT-02`: PASS, 1390 checks

Aggregate scoped result: 9193 PASS, 0 FAIL, 0 BLOCKED.

`HOLE-REUSE-01` was not rerun in V12 because the catalog file `partdesign_holes_updated.CATPart` is absent from `tests/caa_completion/fixtures_manual` and no `*hole*.CATPart` exists under `tests/caa_completion`.

## Full Contract Result

The full completion contract remains intentionally stricter than Phase 1.

- Aggregate for the six rerun fixtures: 9317 PASS, 28 FAIL, 0 BLOCKED
- `PRODUCT-01` and `PRODUCT-02`: full contract PASS
- Part Design failures remain in persistent authoritative Feature-Topology history, generated/modified/consumed relation proof, legacy compatibility capability names, and NURBS coverage when no NURBS surface is present in the fixture.

Runtime identity evidence is retained as runtime survival evidence only. Authoritative history coverage remains 0.0 for the Part Design reruns.

## Capability Highlights

- `native_feature_type_extraction`: complete on the four Part Design reruns.
- `native_feature_parameter_extraction`: complete on the four Part Design reruns.
- `final_brep_topology_extraction`: complete on the four Part Design reruns, including Loop/Coedge output.
- `final_brep_geometry_extraction`: complete on the four Part Design reruns.
- `mesh_generation`: complete on the four Part Design reruns.
- `mesh_brep_face_mapping`: complete on the four Part Design reruns.
- `product_structure_extraction`: complete on PRODUCT-01/02.
- `instance_transform_extraction`: complete on PRODUCT-01/02.
- `feature_final_topology_history`: partial for Part Design, not_available for Product.
- `fta_topology_mapping`: not_available.
- `persistent_generic_naming`: not_available / blocked by lack of verified R21 public authoritative history chain.

## Product Numeric Truth

- `PRODUCT-01`: required instances 2, resolved instances 2, max matrix error 0, max point error 0, max orthogonality error 0, max determinant error 0.
- `PRODUCT-02`: required instances 4, resolved instances 4, max matrix error 0, max point error 0, max orthogonality error 0, max determinant error 0.

## Feature Family Parameter Summary

| Family | Samples | Fully decoded | Partial | Failed | Mandatory coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| pad | 14 | 14 | 0 | 0 | 1.0 |
| plane | 12 | 12 | 0 | 0 | 1.0 |
| pocket | 4 | 4 | 0 | 0 | 1.0 |
| fillet | 1 | 1 | 0 | 0 | 1.0 |
| add | 1 | 1 | 0 | 0 | 1.0 |
| assemble | 1 | 1 | 0 | 0 | 1.0 |
| intersect | 1 | 1 | 0 | 0 | 1.0 |
| remove | 1 | 1 | 0 | 0 | 1.0 |

## B-Rep and Mesh Summary

| Fixture | Faces | Loops | Coedges | Edges | Vertices | Geometry status | Mesh faces | Triangles |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| PD-PAD-01 | 21 | 23 | 102 | 51 | 34 | complete | 21/21 | 96/96 |
| PD-POCKET-01 | 23 | 30 | 96 | 48 | 32 | complete | 23/23 | 592/592 |
| PD-FILLET-01 | 7 | 7 | 30 | 15 | 10 | complete | 7/7 | 28/28 |
| PD-BOOLEAN-01 | 9 | 10 | 36 | 18 | 12 | complete | 9/9 | 132/132 |

Invalid topology references: 0 across these reruns.

