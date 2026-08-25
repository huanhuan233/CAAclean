# CadCapture CAA Bootstrap

CadCapture is a new CATIA V5R21 CAA parser skeleton built under `caa_new`. This stage is a bootstrap only: it establishes the deep-module architecture, command-line entry point, API-independent tests, and a minimal CAA runtime probe.

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
- CAA runtime probe using `Create_Session` and `Delete_Session`.
- Minimal CATPart/CATProduct extension classification without opening native documents.
- Normalized JSON artifact writing for manifest, capture report, and reconstruction plan.
- API-independent VS2008 core tests.

## Not Implemented Yet

- Native CATPart or CATProduct document opening.
- Product recursion.
- Pad, pocket, hole, sketch, FTA, topology, B-Rep, and tessellation extraction.
- Legacy JSONL business projection.

All unavailable native capabilities are reported as bootstrap `not_implemented`; the program does not claim to parse CATIA geometry in this stage.

All headers are indexed. Only verified capabilities are compiled. Only fixture-verified capabilities may be declared implemented. Catalog indexing does not add Frameworks to `IdentityCard` or `Imakefile`; build dependencies stay limited to capabilities used in this stage.

## Suggested Migration Order

1. Move proven session/document open and close handling into the CAA layer.
2. Add document-level metadata extraction.
3. Add product occurrence traversal.
4. Add part feature identity and property facts.
5. Add geometry/topology extraction behind stable model-layer IR.
