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

Normal bootstrap mode writes:

- `manifest.json`
- `capture_report.json`
- `reconstruction_plan.json`

The manifest records `native_document_open_status` as `not_implemented_bootstrap`.
