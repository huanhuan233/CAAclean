@echo off
setlocal

if "%~1"=="" goto usage
set "CASE_NAME=%~1"
set "OUT_DIR=%~2"
if "%OUT_DIR%"=="" set "OUT_DIR=..\fixtures_manual"

set "SCRIPT_DIR=%~dp0"
set "CSCRIPT_BIN=%SystemRoot%\System32\cscript.exe"
if exist "%SystemRoot%\SysWOW64\cscript.exe" set "CSCRIPT_BIN=%SystemRoot%\SysWOW64\cscript.exe"

"%CSCRIPT_BIN%" //nologo "%SCRIPT_DIR%generate_one_advanced_fixture.vbs" --syntax-check
if errorlevel 1 (
  echo [FATAL] VBScript compile check failed. CATIA was not started.
  pause
  exit /b 2
)

echo [GUIDED] %CASE_NAME%
echo CATIA may ask you to click an Edge or Face. Follow the prompt in CATIA.
"%CSCRIPT_BIN%" //nologo "%SCRIPT_DIR%generate_one_advanced_fixture.vbs" "%OUT_DIR%" "%CASE_NAME%" guided
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

:usage
echo Usage: run_one_guided.bat CASE [fixture-directory]
echo Cases: fillet chamfer shell_thickness pressure
echo Example: run_one_guided.bat fillet "..\fixtures_manual"
exit /b 2
