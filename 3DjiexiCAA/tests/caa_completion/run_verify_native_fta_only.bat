@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "GEN_DIR=%SCRIPT_DIR%generators"
set "CSCRIPT_BIN=%SystemRoot%\SysWOW64\cscript.exe"

if "%~1"=="" (
  set "OUT_DIR=%SCRIPT_DIR%fixtures_manual"
) else (
  set "OUT_DIR=%~1"
)

if not exist "%CSCRIPT_BIN%" (
  echo [ERROR] Required 32-bit cscript not found: %CSCRIPT_BIN%
  exit /b 2
)

echo [INFO] Output directory: %OUT_DIR%
echo [INFO] Using: %CSCRIPT_BIN%

echo [STEP] Syntax precheck: verify_native_fta_fixtures.vbs
"%CSCRIPT_BIN%" //nologo "%GEN_DIR%\verify_native_fta_fixtures.vbs" --syntax-check
if errorlevel 1 exit /b %errorlevel%

echo [STEP] Read-only native FTA verification
"%CSCRIPT_BIN%" //nologo "%GEN_DIR%\verify_native_fta_fixtures.vbs" "%OUT_DIR%"
exit /b %errorlevel%
