# CadCapture CAA New Architecture

CadCapture is a new CATIA V5R21 CAA parser built under `caa_new`. Phase 1A opens CATPart/CATProduct documents through CAA in read-only mode and captures a lossless CATPart object tree without migrating feature, topology, tessellation, FTA, product-recursion, or sketch extraction.

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
- Normalized JSON artifact writing for manifest, capture report, reconstruction plan, `object_entities.jsonl`, and `tree_occurrences.jsonl`.
- Legacy projection writing for compatible `features.jsonl` and `relations.jsonl`.
- API-independent VS2008 core tests.

## Not Implemented Yet

- Product recursion.
- Pad, pocket, hole, sketch, FTA, topology, B-Rep, and tessellation extraction.

All unavailable native capabilities are reported as Phase 1A `not_implemented`; the program does not claim to parse CATIA geometry in this stage. Ordinary CATPart input must come from the real CAA document tree and must not produce a bootstrap placeholder part root.

All headers are indexed. Only verified capabilities are compiled. Only fixture-verified capabilities may be declared implemented. Catalog indexing does not add Frameworks to `IdentityCard` or `Imakefile`; build dependencies stay limited to capabilities used in this stage.

## Suggested Migration Order

1. Verify more real CATPart fixtures against the old parser node count.
2. Add document-level metadata extraction.
3. Add product occurrence traversal.
4. Add part feature identity and property facts.
5. Add geometry/topology extraction behind stable model-layer IR.
