# CAA Feature Decoder V14 Completeness Evidence

Scope: feature parameter decoder completeness for the current CATIA V5R21 x86 parser build. No formal CATPart or CATProduct fixture was regenerated, overwritten, or modified.

## Build And Tests

- R21 x86 `mkmk` build: PASS via `tools/build_r21_x86.bat`.
- Python validator unit tests: PASS, 27 tests.
- VS2008/C++03 core self-tests: PASS.

## Real CATIA Runs

Run root: `tests/caa_completion/results_local_v14_feature_decoder`.

| Fixture | Input | Validated complete families |
| --- | --- | --- |
| HOLE-REUSE-01 | `tests/fixtures/catia_r21/partdesign_holes_updated.CATPart` | hole 5, pad 1, pocket 1 |
| PD-CHAMFER-01 | `tests/caa_completion/fixtures_manual/pd_chamfer_variants.CATPart` | chamfer 1 |
| PD-REVOLVE-01 | `tests/caa_completion/fixtures_manual/pd_shaft_groove.CATPart` | shaft 1, groove 1 |
| PD-SWEEP-01 | `tests/caa_completion/fixtures_manual/pd_rib_slot.CATPart` | rib 1, slot 1 |
| PD-SHELL-01 | `tests/caa_completion/fixtures_manual/pd_shell_thickness.CATPart` | shell 1, thickness 1 |
| PD-PATTERN-01 | `tests/caa_completion/fixtures_manual/pd_patterns.CATPart` | rectangular_pattern 1 |
| PD-FILLET-01 | `tests/caa_completion/fixtures_manual/pd_fillet_constant.CATPart` | constant edge fillet 1 |
| PD-BOOLEAN-01 | `tests/caa_completion/fixtures_manual/pd_multibody_booleans.CATPart` | add 1, remove 1, assemble 1, intersect 1 |
| PRESSURE-01 | `tests/caa_completion/fixtures_manual/pressure_pad_pocket_fillet_chamfer.CATPart` | fillet 1, chamfer 1 |

## Public API Evidence

- Hole: `CATIAHole`.
- Chamfer: `CATIAChamfer`.
- Draft: compiled branch uses `CATIADraft`, `CATIADraftDomains`, `CATIADraftDomain`.
- Shell and Thickness: `CATIAShell`, `CATIAThickness`.
- Shaft and Groove: `CATIARevolution`; when `get_RevoluteAxis` is unavailable, the parser records profile sketch and center line through `CATIShapeFeatureProperties.GiveMeYourFavoriteSketches` plus `CATISketch.GetCurrentCenterLine`.
- Rib and Slot: `CATIASweep`.
- Pattern: `CATIARectPattern`, `CATIACircPattern`, `CATIAUserPattern`; formal evidence currently covers only `CATIARectPattern`.
- Fillet: `CATIAConstRadEdgeFillet`, with compiled branches for `CATIAVarRadEdgeFillet`, `CATIAFaceFillet`, and `CATIATritangentFillet`.

## Blocked Or Not Yet Formally Validated

- Draft: `tests/caa_completion/fixtures_manual/pd_draft_variants.CATPart` is absent.
- Variable, face and tritangent fillet: `tests/caa_completion/fixtures_manual/pd_fillet_advanced.CATPart` is absent.
- Circular and user pattern: `pd_patterns.CATPart` contains `RectPattern.1` only. The validator still fails `PD-PATTERN-01` against the full catalog because `circular_pattern` and `user_pattern` are expected but missing from the formal fixture.

These are not reported as complete from source code alone.
