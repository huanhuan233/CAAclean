# CAA B-Rep V15/V16 Incremental Evidence

Source workspace baseline: `40d4237 Complete advanced feature parameter decoder evidence`.

This evidence records B-Rep-specific incremental work only. It does not seal CAA V1, does not claim completion of persistent Feature-Topology history, FTA mapping, or full completion contract requirements that remain outside the B-Rep scope.

## Implementation

- Added R21 Public API NURBS parameter extraction via `CATNurbsSurface`, `CATNurbsCurve` and `CATKnotVector`.
- Added `CATSurface.GetGeometricRep()` plane fallback for offset shell faces.
- Added coedge ring fields: `previous_coedge_id` and `next_coedge_id`.
- Finalized Face-Edge, Edge-Face and Face-Face reverse topology links after all cells are collected.
- Hardened capability and validator checks for closed coedge rings, wire/coedge consistency, reverse Face-Edge links and symmetric Face-Face adjacency.
- Added R21 Public `CATSurface.GetLimits` / `CATCurve.GetLimits` parameter-domain extraction for Face and Edge geometry rows.
- Added Face material-side evidence from `CATCell::CreateBoundedCellsIterator` and `CATSide`.
- Replaced the previous boundary-iterator-cycle closure label with `closed_by_edge_vertex_continuity`, requiring adjacent wire Edges to share Vertex cells before a Wire can support `final_brep_topology_extraction=complete`.
- Hardened `final_brep_geometry_extraction=complete` so exact Face/Edge rows also require parameter domains, and Faces require non-unknown material side.

## Verification Commands

```text
python -m unittest tests.caa_completion.tests.test_validator -v
cmd /c tools\test_core_vs2008.bat
cmd /c "set CAA_RADE_ROOT=D:\CATIA\Rade21&& set CAA_PREREQ_ROOT=D:\CATIA&& set CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings&& set RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE&& tools\build_r21_x86.bat"
cmd /c "set CAA_RADE_ROOT=D:\CATIA\Rade21&& set CAA_PREREQ_ROOT=D:\CATIA&& tools\run_r21_x86.bat --input tests\caa_completion\fixtures_manual\pd_shell_thickness.CATPart --output tests\caa_completion\results_local_v16_incremental_brep\PD-SHELL-01_A --read-only"
python tests\caa_completion\tools\run_phase1_suite.py --results-dir tests\caa_completion\results_local_v16_incremental_brep --catalog tests\caa_completion\spec\fixture_catalog.json --contract tests\caa_completion\contracts\caa_v1_phase1_contract.json --output tests\caa_completion\results_local_v16_incremental_brep\phase1_report.json
```

## Results

| Fixture | Topology | Geometry | Analytic Surfaces | Curves | Mesh-Face | Face/Loop/Coedge |
| --- | --- | --- | --- | --- | --- | --- |
| PD-PAD-01 | complete | complete | complete | complete | complete | 21 / 23 / 102 |
| PD-FILLET-01 | complete | complete | complete | complete | complete | 7 / 7 / 30 |
| PD-BOOLEAN-01 | complete | complete | complete | complete | complete | 9 / 10 / 36 |
| PD-SHELL-01 | complete | complete | complete | complete | complete | 11 / 12 / 48 |
| MEASURE-ANALYTIC-01 | complete | complete | complete | complete | complete | 9 / 10 / 36 |
| NEG-SURFACE-01 | not_available | not_available | not_available | not_available | not_available | no main-solid topology |

`nurbs_surface_parameter_extraction` remains `not_available` in these real runs because the current formal fixtures do not expose main-solid NURBS faces. The decoder branch is compiled and linked against R21 Public headers, but it is not counted as real-run complete without a NURBS topology fixture.

The V16 local shell run additionally emitted `parameter_domain` for all exact Face/Edge rows and non-unknown `material_side` for all Faces in `PD-SHELL-01_A`; its inner and outer loops were closed by Edge-Vertex continuity.

The same incremental validation promoted field-level Feature payload contracts for Chamfer, Shell, Thickness, Shaft, Groove, Rib and Slot. Rib/Slot profile references are read through R21 Public `CATISweep.GetProfile` / `CATISweep.GetCenterCurve`; center-curve element references remain available through Automation `CATIASweep.get_CenterCurveElement`.

Full completion-contract validation still reports expected failures for persistent Feature-Topology history and related authoritative relation semantics. Those failures were not hidden or downgraded. Remaining work before final sealing includes Pattern formal fixture coverage for circular/user patterns, Draft and advanced Fillet formal fixtures, broader real Shell coverage, trimmed UV-loop semantics, numeric measurement cross-checks against CATIA measures, curvature sampling, and a formal NURBS topology fixture.
