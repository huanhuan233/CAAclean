@echo off
setlocal

set "OUT_DIR=%~1"
if "%OUT_DIR%"=="" set "OUT_DIR=..\fixtures_manual"

set "SCRIPT_DIR=%~dp0"
set "CSCRIPT_BIN=%SystemRoot%\System32\cscript.exe"
if exist "%SystemRoot%\SysWOW64\cscript.exe" set "CSCRIPT_BIN=%SystemRoot%\SysWOW64\cscript.exe"

echo [INFO] CATIA V5R21 remaining advanced-fixture repair
echo [INFO] Output: %OUT_DIR%
echo [INFO] Running only: fillet, chamfer, shaft_groove, shell_thickness, pressure
echo [INFO] Preserving passed fixtures: rib_slot, pattern, gsd_analytic, boolean
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

for %%C in (fillet chamfer shaft_groove shell_thickness pressure) do (
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
