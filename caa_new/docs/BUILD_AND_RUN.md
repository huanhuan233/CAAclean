# Build And Run

Run commands from:

```bat
cd /d H:\PXY2\3Djiexi\freecadCAA\caa_new
```

## Core Tests

```bat
call tools\test_core_vs2008.bat
```

Output:

```text
build_core\CaptureCoreTests.exe
```

These tests compile only API-independent modules and do not require CATIA headers.

## CAA Build

```bat
call tools\build_r21_x64.bat
```

Required environment:

- `CAA_RADE_ROOT`
- `CAA_PREREQ_ROOT`

The script uses RADE host tools from `intel_a`, sets `_MkmkOS_BitMode=64`, selects the VS2008 x64 compiler, calls `MkmkSetenv.bat`, `mkGetPreq.bat`, and `mkmk.bat`, writes `build_r21_x64.log`, scans for common compiler/linker errors, and checks:

```text
win_b64\code\bin\CadCapture.exe
```

## Runtime Commands

```bat
call tools\run_r21_x64.bat --self-test
call tools\run_r21_x64.bat --probe-runtime
call tools\run_r21_x64.bat --input "H:\PXY2\3Djiexi\freecadCAA\caa_new\tests\dummy.CATPart" --output "H:\PXY2\3Djiexi\freecadCAA\caa_new\selftest_output" --pretty
```

Normal Phase 1A mode writes through a staging directory and commits the output transaction only after required files and JSONL counts are verified:

- `manifest.json`
- `capture_report.json`
- `reconstruction_plan.json`
- `object_entities.jsonl`
- `tree_occurrences.jsonl`
- `product_references.jsonl`
- `product_occurrences.jsonl`
- `document_links.jsonl`
- `features.jsonl`
- `relations.jsonl`

The manifest records `native_document_open_status` as `opened_read_only` when CAA opens the native document successfully.

## CATPart Tree Comparison

Compare a real CATPart against the legacy parser without comparing unstable IDs:

```powershell
powershell -ExecutionPolicy Bypass -File tools\compare_catpart_tree.ps1 `
  -OldExe "H:\PXY2\3Djiexi\freecadCAA\3DjiexiCAA\win_b64\code\bin\CadParseMvp.exe" `
  -NewExe "H:\PXY2\3Djiexi\freecadCAA\caa_new\win_b64\code\bin\CadCapture.exe" `
  -Input "H:\model\sample.CATPart" `
  -OldOutput "H:\output\old_tree" `
  -NewOutput "H:\output\new_tree" `
  -ReportOutput "H:\output\tree_comparison.json"
```

## CATProduct Tree Comparison

Compare a real CATProduct against the legacy parser without comparing unstable IDs:

```powershell
powershell -ExecutionPolicy Bypass -File tools\compare_catproduct_tree.ps1 `
  -OldExe "H:\PXY2\3Djiexi\freecadCAA\3DjiexiCAA\win_b64\code\bin\CadParseMvp.exe" `
  -NewExe "H:\PXY2\3Djiexi\freecadCAA\caa_new\win_b64\code\bin\CadCapture.exe" `
  -Input "H:\model\assembly.CATProduct" `
  -OldOutput "H:\output\old_product" `
  -NewOutput "H:\output\new_product" `
  -ReportOutput "H:\output\product_comparison.json"
```

The Phase 1B comparison checks instance path coverage, duplicate paths, instance names, transform availability, product reference links, and legacy relation endpoint validity. It does not yet require linked CATPart definitions below every product instance because that capability is not fixture-verified.

## Catalog Tools

Regenerate the local R21 SDK index:

```powershell
powershell -ExecutionPolicy Bypass -File tools\generate_r21_api_catalog.ps1
```

Query a header, Framework, or capability:

```powershell
powershell -ExecutionPolicy Bypass -File tools\find_r21_api.ps1 -Query CATSession
```
