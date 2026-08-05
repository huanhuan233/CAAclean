@echo off
setlocal

set "OUT_DIR=%~1"
if "%OUT_DIR%"=="" set "OUT_DIR=..\fixtures_manual"

set "SCRIPT_DIR=%~dp0"
set "CSCRIPT_BIN=%SystemRoot%\System32\cscript.exe"
if exist "%SystemRoot%\SysWOW64\cscript.exe" set "CSCRIPT_BIN=%SystemRoot%\SysWOW64\cscript.exe"

echo [INFO] CATIA V5R21 advanced-fixture standalone repair v1.0.3
echo [INFO] Output: %OUT_DIR%
echo [INFO] Existing files are backed up and replaced only after close/reopen verification.
echo.

echo [PREFLIGHT] Compile-checking VBScript before starting CATIA cases...
"%CSCRIPT_BIN%" //nologo "%SCRIPT_DIR%generate_one_advanced_fixture.vbs" --syntax-check
if errorlevel 1 (
  echo [FATAL] VBScript compile check failed. No fixture case was started.
  echo.
  pause
  exit /b 2
)
echo.

for %%C in (fillet chamfer shaft_groove rib_slot shell_thickness pattern boolean gsd_analytic pressure) do (
  echo ============================================================
  echo [CASE] %%C
  "%CSCRIPT_BIN%" //nologo "%SCRIPT_DIR%generate_one_advanced_fixture.vbs" "%OUT_DIR%" %%C
  if errorlevel 1 (
    echo [CASE-FAILED] %%C -- existing fixture, if any, was preserved.
  ) else (
    echo [CASE-PASSED] %%C
  )
  echo.
)

echo ============================================================
echo [DONE] Inspect:
echo   %OUT_DIR%\advanced_repair_ledger.tsv
echo   %OUT_DIR%\generation_ledger.tsv
echo.
pause
endlocal
