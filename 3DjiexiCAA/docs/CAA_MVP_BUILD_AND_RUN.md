# Build and Run on CATIA/CAA V5R21

Required environment: CATIA V5R21, CAA RADE V5R21, Visual Studio 2008 SP1, Win32/x86, and a valid local RADE license setting.

From a Visual Studio/RADE-capable command prompt:

```bat
set CAA_RADE_ROOT=<CAA RADE V5R21 root>
set CAA_PREREQ_ROOT=<CATIA V5R21 root>
set RADECATSettingPath=<directory containing the registered RADE CATSettings>
call tools\build_r21_x86.bat
```

The script forces `_MkmkOS_BitMode=32`, runs `mkGetPreq`, targets `CadParseMvp.edu CadParseMvp.m`, scans the build log for the R21 behavior where `mkmk` can return zero despite `make-ERROR`, and verifies the executable exists.

Run license-free tests either directly with VS2008 or inside the CAA runtime:

```bat
call tools\test_core_vs2008.bat
call tools\run_r21_x86.bat --self-test
```

Parse a CATPart:

```bat
call tools\run_r21_x86.bat --input "D:\models\sample.CATPart" --output "D:\parse-output\sample" --read-only --pretty
```

The parser always opens CATPart read-only. It writes `manifest.json`, `features.jsonl`, `relations.jsonl`, `diagnostics.json`, `coverage.json`, and `parser.log`. A missing input, wrong extension, session/open failure, unwritable output, traversal fatal error, or coverage mismatch returns a non-zero code.

The run script launches the built executable with the workspace and CATIA Win32 runtime directories on `PATH`. This is intentional: the installed R21 `mkrun` wrapper was observed to discard the child process exit code, while direct execution preserves the parser's documented fatal exit codes.

Command-line paths are interpreted using the process locale by the R21 `CATUnicodeString(const char*)` constructor. Object names are converted back to UTF-8 with the documented `ConvertToUTF8` API. Full Unicode CLI path handling remains `TODO(R21_API_VERIFY)` for the fixed R21 batch launcher.
