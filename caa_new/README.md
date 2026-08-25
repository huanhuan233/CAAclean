# CadCapture CAA New Architecture

CadCapture is a new CATIA V5R21 CAA parser built under `caa_new`. It opens native CATPart/CATProduct documents through CAA in read-only mode, preserves CATPart trees, captures CATProduct product structure, and migrates the verified evidence-level topology, tessellation, ResultOUT, property, and FTA/TPS set paths from the legacy parser.

Current legacy migration status is tracked in `docs\MIGRATION_STATUS.md`.

## Build

Use the R21 x86 tools from this directory:

```bat
cd /d H:\PXY2\3Djiexi\freecadCAA\caa_new
call tools\test_core_vs2008.bat
call tools\build_r21_x64.bat
```

The RADE host tools run from `intel_a`, while the target is `win_b64` with `_MkmkOS_BitMode=64`. The executable is written to:

```text
H:\PXY2\3Djiexi\freecadCAA\caa_new\win_b64\code\bin\CadCapture.exe
```

## Run

```bat
call tools\run_r21_x64.bat --self-test
call tools\run_r21_x64.bat --probe-runtime
call tools\run_r21_x64.bat --input "H:\model\sample.CATPart" --output "H:\output\sample" --pretty
```

## Implemented Now

- Pure data model for documents, objects, occurrences, properties, semantic facts, geometry, topology, PMI, diagnostics, and reconstruction package.
- SDK Catalog and Capability Coverage data structures, JSON files, query tools, and API-independent tests.
- `ModelCaptureEngine` as the only top-level orchestration entry point.
- CAA runtime probe and guarded session lifetime using `Create_Session` and `Delete_Session`.
- Guarded document lifetime using `CATDocumentServices::OpenDocument` and read-only native document handles.
- CATPart tree enumeration from the real `CATDocument` using `CATInit`, `CATIPrtContainer`, `CATIPrtContainer::GetPart`, `CATISpecObject::ListComponents`, and `CATIContainer::ListMembersHere`.
- Lossless object and occurrence preservation for recognized and unknown CATIA objects.
- Primary tree and supplemental discovery are separated; supplemental nodes are preserved but not promoted to extra roots.
- CATProduct traversal from the real `CATDocument` through `CATIDocRoots`, `CATIProduct::GetReferenceProduct`, `GetPrdInstanceName`, `GetPartNumber`, `GetChildren`, and `CATIMovable::GetAbsPosition`.
- Product reference and product occurrence are stored separately, so multiple instances can share one reference while retaining unique occurrence paths.
- Referenced CATPart documents exposed through `CATILinkableObject::GetDocument` are registered in `DocumentGraph`, captured once as definitions, and projected under each product instance with independent feature occurrences.
- `PropertyFact` output for captured document, object, occurrence, and product instance identity/status fields, plus legacy-compatible `parameters.jsonl` projection from those facts.
- Type-only native feature semantic facets from captured `startup_type` values, with explicit canonical family, decoder ID, decode level, and payload availability; these are also projected to legacy-compatible `native_features.jsonl`.
- Root CATPart final `CATBody` topology capture through `CATIPrtPart::GetSolid`, including body cell counts, face/edge/vertex/volume cell summaries, face area, edge length, cell center evidence, and face tessellation range summaries.
- Shape feature ResultOUT body summaries through `CATIShapeFeatureBody::GetResultOUT` and `CATIGeometricalElement::GetBodyResult`, linked back to captured ObjectEntity IDs through `feature_dependencies.jsonl`.
- FTA/TPS set-level evidence through `CATITPSDocument::GetSets`, with normalized `pmi_entities.jsonl` and legacy-compatible `fta_sets.jsonl`. Empty TPS Set results are preserved as empty files, not failures.
- Normalized JSON artifact writing for manifest, capture report, reconstruction plan, `object_entities.jsonl`, `tree_occurrences.jsonl`, `product_references.jsonl`, `product_occurrences.jsonl`, and `document_links.jsonl`.
- Legacy tree projection writing for compatible `features.jsonl` and `relations.jsonl` with occurrence IDs as feature IDs. CATProduct parent relations are also projected as `contains`.
- Transactional artifact commit through `ArtifactRepository`.
- New/old CATPart tree comparison with `tools\compare_catpart_tree.ps1`.
- New/old CATProduct tree comparison with `tools\compare_catproduct_tree.ps1`.
- Phase 7 regression wrapper with `tools\validate_phase7_parity.ps1`.
- API-independent VS2008 core tests.

## Not Implemented Yet

- Broken or unloaded external link recovery beyond documents already exposed by CATIA Public APIs.
- Recursive parsing of linked CATProduct definitions beyond the root product tree.
- Full properties, native Feature parameter payloads, Pad, Pocket, Hole, Sketch, detailed FTA semantics, FTA-to-topology links, exact surface/curve parameter extraction, ResultOUT cell-to-final-face mapping, full B-Rep graph, and triangle payload extraction.
- CATIInertia and Knowledgeware parameter values from legacy code are not yet migrated in this branch; unavailable tabs are not fabricated.

Unavailable native capabilities remain explicit in diagnostics or capability coverage; the program does not claim to parse CATIA geometry in this stage. Ordinary CATPart input must come from the real CAA document tree and must not produce a bootstrap placeholder part root.

All headers are indexed. Only verified capabilities are compiled. Only fixture-verified capabilities may be declared implemented. Catalog indexing does not add Frameworks to `IdentityCard` or `Imakefile`; build dependencies stay limited to capabilities used in this stage.

## Suggested Migration Order

1. Verify more real CATPart fixtures against the old parser node count.
2. Add document-level metadata extraction.
3. Resolve external linked product documents.
4. Project CATPart feature definitions below product instances without parsing the same reference repeatedly.
5. Add part feature identity and property facts.
6. Add geometry/topology extraction behind stable model-layer IR.
