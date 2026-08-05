# CAA completion suite report

Overall: **FAIL**

| Package | PASS | FAIL | BLOCKED | BLOCKED_FIXTURE_R21 | UNTESTED_NO_FIXTURE |
|---|---:|---:|---:|---:|---:|
| boundary_negative | 1 | 0 | 1 | 0 | 0 |
| business_connections | 2 | 0 | 0 | 0 | 0 |
| catproduct | 2 | 0 | 3 | 0 | 0 |
| feature_registry | 2 | 1 | 0 | 0 | 0 |
| fta_mbd | 0 | 0 | 0 | 3 | 0 |
| gsd_native | 0 | 1 | 1 | 0 | 0 |
| manufacturing_geometry_evidence | 1 | 1 | 1 | 0 | 0 |
| native_part_design | 6 | 4 | 8 | 0 | 0 |
| properties_measurement | 1 | 1 | 0 | 0 | 0 |
| topology_mapping_pressure | 0 | 1 | 2 | 0 | 0 |
| version_pairs | 7 | 2 | 0 | 0 | 2 |

## Non-passing fixtures

- `FTA-NEGATIVE-01` — BLOCKED_FIXTURE_R21:  
- `FTA-REFERENCE-01` — BLOCKED_FIXTURE_R21:  
- `FTA-SEMANTICS-01` — BLOCKED_FIXTURE_R21:  
- `GEO-CAVITY-02` — BLOCKED:  
- `GEO-SLOT-STEP-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: groove
- `GSD-ANALYTIC-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: gsd_extrude
- `GSD-COMPLEX-01` — BLOCKED:  
- `MEASURE-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: point
- `NEGATIVE-02` — BLOCKED:  
- `PD-BOOLEAN-01` — FAIL: FEATURE_RELATION_KINDS missing relation kinds for fixture roles: ['consumed', 'modified']
- `PD-BOOLEAN-02` — BLOCKED:  
- `PD-CHAMFER-01` — FAIL: FEATURE_RELATION_KINDS missing relation kinds for fixture roles: ['consumed', 'modified']
- `PD-DRAFT-01` — BLOCKED:  
- `PD-FILLET-01` — FAIL: FEATURE_RELATION_KINDS missing relation kinds for fixture roles: ['consumed', 'modified']
- `PD-FILLET-02` — BLOCKED:  
- `PD-PAD-02` — BLOCKED:  
- `PD-PATTERN-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: circular_pattern
- `PD-POCKET-02` — BLOCKED:  
- `PD-RIBS-01` — BLOCKED:  
- `PD-SWEEP-02` — BLOCKED:  
- `PD-TRANSFORM-01` — BLOCKED:  
- `PRESSURE-01` — FAIL: FEATURE_RELATION_KINDS missing relation kinds for fixture roles: ['consumed', 'merged', 'modified', 'split']
- `PRESSURE-02` — BLOCKED:  
- `PRESSURE-03` — BLOCKED:  
- `PRODUCT-03` — BLOCKED:  
- `PRODUCT-04` — BLOCKED:  
- `PRODUCT-NEG-01` — BLOCKED:  
- `REGISTRY-STATUS-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: pocket
- `VERSION-FTA-01` — UNTESTED_NO_FIXTURE:  
- `VERSION-FTA-01` — UNTESTED_NO_FIXTURE:  
- `VERSION-PART-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: fillet
- `VERSION-PART-01` — FAIL: FIXTURE_NATIVE_EXPECTED expected decoded native type missing: fillet
