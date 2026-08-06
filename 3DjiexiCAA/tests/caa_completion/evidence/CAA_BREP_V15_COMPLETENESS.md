# CAA B-Rep V15 Completeness Evidence

Source workspace baseline: `40d4237 Complete advanced feature parameter decoder evidence`.

This evidence records the B-Rep-specific work only. It does not claim completion of persistent Feature-Topology history, FTA mapping, or full completion contract requirements that remain outside the B-Rep scope.

## Implementation

- Added R21 Public API NURBS parameter extraction via `CATNurbsSurface`, `CATNurbsCurve` and `CATKnotVector`.
- Added `CATSurface.GetGeometricRep()` plane fallback for offset shell faces.
- Added coedge ring fields: `previous_coedge_id` and `next_coedge_id`.
- Finalized Face-Edge, Edge-Face and Face-Face reverse topology links after all cells are collected.
- Hardened capability and validator checks for closed coedge rings, wire/coedge consistency, reverse Face-Edge links and symmetric Face-Face adjacency.

## Verification Commands

```text
python -m unittest tests.caa_completion.tests.test_validator -v
cmd /c tools\test_core_vs2008.bat
cmd /c "set CAA_RADE_ROOT=D:\CATIA\Rade21&& set CAA_PREREQ_ROOT=D:\CATIA&& set CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings&& set RADECATSettingPath=%APPDATA%\DassaultSystemes\CATSettings\RADE&& tools\build_r21_x86.bat"
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

Full completion-contract validation still reports expected failures for persistent Feature-Topology history and related authoritative relation semantics. Those failures were not hidden or downgraded.
