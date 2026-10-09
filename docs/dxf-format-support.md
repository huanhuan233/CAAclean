# DXF format branch

## Architecture and contract

Upload identifies `.dxf` case insensitively and persists `source_format=DXF` and `processing_route=dxf_cad_parse` on the existing CAD Revision. The route launches the host Python reader in an isolated, timed subprocess; it never calls CATIA or the STEP parser. The reader emits neutral JSON. A separate FreeCADCmd job validates planar Wires and Faces without loading the DXF importer or a GUI. The same Revision, PostgreSQL evidence table, protected viewer asset route, retry endpoint, and error lifecycle serve all three formats.

The DXF Viewer contract has `viewer_kind=drawing_2d`. Its required asset is `viewer_asset.scene_url`, bound to `task_id` and `dxf.source_sha256`. Existing 3D contracts retain `viewer_kind=model_3d` and still require GLB, scene manifest, and both mesh maps. DXF has an empty assembly contract (`assembly_mode=none`), no Solid, and no manufactured mesh assets.

The scene schema is `dxf_document_v1`. It records the source SHA-256, DXF version and encoding, `$INSUNITS` or `drawing_unit`, layouts, source-defined layers, definitions, source entities, derived block occurrences, diagnostics, and counts. An entity ID includes Revision, layout, and source handle. Virtual block geometry has `derived=true`, a definition handle when available, and a stable occurrence path. It never claims a virtual handle is a source handle. The source entity list and expanded occurrence list are distinct. The browser obtains its object list through paginated PostgreSQL queries at `/api/component-builds/{build_id}/viewer/dxf/dxf_entities` and `dxf_occurrences`; it loads the version-bound scene asset for vector display.

| Format | Route | Inspection | Geometry | Viewer |
| --- | --- | --- | --- | --- |
| CATPart/CATProduct | `catia_feature_center` | CAA native | CATIA export plus existing sidecar | 3D |
| STEP/STP | `step_cad_parse` | STEP/FreeCAD | existing FreeCAD route | 3D |
| DXF | `dxf_cad_parse` | ezdxf host subprocess | neutral curves to FreeCADCmd | 2D |

## Current capabilities and limits

POINT, LINE, ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE retain coordinates, handles, layer and source properties. LWPOLYLINE keeps all vertices, bulges, widths, elevation and extrusion; WCS vertices are recorded separately. Bulge arcs, including the closing segment and major arcs, are rendered as circular SVG arcs. Straight and curved segment lengths and single closed contour areas are calculated in drawing units. Closed polyline areas are published only after a valid FreeCAD Face independently agrees with the analytical value. The normalized mm/mm² values are null when units are unknown. Source contours are not automatically combined into holes or business regions.

INSERT/MINSERT preserve insert properties and ATTRIBs. Bounded virtual occurrences have separate identities. A block cycle, depth limit, array budget, invalid reference, or transformation failure produces a diagnostic. TEXT/MTEXT preserve raw and display text; font references are metadata only. DIMENSION stores source text, display text, actual measurement and style overrides separately. HATCH keeps source boundary paths and fill settings; a simple single closed solid hatch can display as a translucent fill. ELLIPSE and SPLINE retain source properties and a display approximation with declared tolerance; that approximation is **not** an exact measurement. Model and paper layouts are listed separately. Unsupported viewports, external images/PDF underlays, proxy objects, and proprietary solids remain diagnostic source records. No external paths or URLs are loaded by the parser.

The current 2D display uses selectable SVG vectors inside the existing Viewer page shell, with orthographic view, wheel zoom, pan, fit, layer toggles, search, list selection and a 400px detail column. Color support covers the common ACI colors and selection restores the layer color. Advanced linetypes, complete font metrics, arbitrary viewport clipping, full HATCH pattern rendering, curve to curve witness-point distance, cross-format mapping and combined-region boolean measurements are not implemented. These are not advertised as completed capabilities. A FreeCAD failure retains source browsing, sets dependent area values to undefined, and records a diagnostic. `dxf.completeness=partial` records unsupported or failed content; a ready source scene can still be opened.

## Offline deployment

Use the backend's host Python, not FreeCAD's bundled Python, for `ezdxf`. `backend/requirements.txt` pins `ezdxf==1.4.2`; `backend/requirements-dxf.lock` records the tested direct runtime dependencies. For an offline target, prepare wheels on a connected staging machine matching the **target Python version, OS and architecture**. For example, with Python 3.12:

```powershell
python -m pip download --only-binary=:all: --platform win_amd64 --python-version 3.12 --implementation cp --abi cp312 -d wheelhouse/win_amd64 -r backend/requirements-dxf.lock
python -m pip download --only-binary=:all: --platform manylinux_2_17_aarch64 --python-version 3.12 --implementation cp --abi cp312 -d wheelhouse/linux_aarch64 -r backend/requirements-dxf.lock
```

Prepare the rest of `backend/requirements.txt` for each target in the same manner, including locally approved transitive wheels. Install from the corresponding directory with `pip install --no-index --find-links <wheelhouse> -r backend/requirements.txt -r backend/requirements-dxf.lock`. Do not mix Windows wheels with Linux aarch64 wheels. The existing `FREECAD_CMD`, `FREECAD_TIMEOUT`, upload size, and work directory settings are reused. No CATIA setting is required for DXF. The FreeCAD script uses `Part` in background mode. Runtime makes no public network request. Provide any licensed fonts separately through the deployment environment; font fallback does not prove layout fidelity.

Retry reuses the saved source Revision and replaces only generated `dxf/` output and this Revision's `dxf_*` evidence categories. Old results retain their own Revision ID and scene hash. A bad DXF header, parser error or changed source hash fails the task explicitly. Unsupported entities do not delete successful source records.

## Acceptance evidence (2026-10-09)

The private `stopoff3.dxf` read from a user-supplied local path has SHA-256 `d2bf3913618fb554a28611504fd5bfdf5fc17d418c70432df8ee4e2183aab532`. It was not copied into Git. Source reading returned AC1015, `$INSUNITS=4`, 103 closed LWPOLYLINEs, 1707 vertices, longest polyline 730 vertices, and zero unsupported or failed entities. Four source layers were detected; `Defpoints` was marked as parser-added. No DIMENSION or HATCH was synthesized. Background FreeCAD validated all 103 Wires/Faces; maximum analytical/FreeCAD area difference was about `5.1e-11` drawing units². The source hash was unchanged after reading.

An isolated PostgreSQL database and local backend served the original DXF through the normal upload API. The task reached `ready` with `viewer_kind=drawing_2d`, `dxf.completeness=complete`, 103 source entities and 103 FreeCAD-validated geometries. The paginated evidence endpoint returned 50 records on the first page, 3 on the last page, and the correct record for an exact handle lookup. Retrying the saved Revision reached `ready` again. The source and controlled-copy SHA-256 values matched the original after processing.

In Chrome, the Feature Center displayed 103 selectable vectors. List selection and direct vector selection both opened the matching PostgreSQL-backed entity detail. Layer hiding removed the vectors and cleared selection; layer restoration, handle search, Model/Layout1 switching, zoom, pan and the 400px detail column were inspected. A STEP fixture processed in the same isolated service and opened with `viewer_kind=model_3d`; switching back showed the DXF workspace again. Chrome's file chooser could not access the local source because its browser extension lacked file-URL access, so this acceptance upload used the same isolated backend HTTP endpoint. The browser upload gesture is not counted as passed.

Targeted backend source, semantic, geometry, component-build API and CAD service tests passed (46 passed). Frontend DXF path tests, TypeScript typecheck and production build passed. The full backend suite had unrelated pre-existing failures and is not counted as passing; see the task report for its counts.
