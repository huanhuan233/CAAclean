@echo off
setlocal

rem Reopens both fixtures in CATIA, verifies native interfaces, then writes hashes and manifest.
set "FIXTURE_DIR=%~1"
if "%FIXTURE_DIR%"=="" set "FIXTURE_DIR=%~dp0..\tests\fixtures\catia_r21"
set "REPORT_FILE=%TEMP%\cadparse_r21_fixture_%RANDOM%_%RANDOM%.properties"
set "CSCRIPT=%SystemRoot%\SysWOW64\cscript.exe"
if not exist "%CSCRIPT%" set "CSCRIPT=%SystemRoot%\System32\cscript.exe"

"%CSCRIPT%" //nologo "%~dp0verify_partdesign_hole_fixtures.vbs" "%FIXTURE_DIR%" "%REPORT_FILE%"
if errorlevel 1 (
  set "VERIFY_EXIT=%errorlevel%"
  if exist "%REPORT_FILE%" del /q "%REPORT_FILE%"
  exit /b %VERIFY_EXIT%
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_partdesign_hole_fixture_manifest.ps1" -FixtureDirectory "%FIXTURE_DIR%" -VerificationReport "%REPORT_FILE%"
set "MANIFEST_EXIT=%errorlevel%"
if exist "%REPORT_FILE%" del /q "%REPORT_FILE%"
exit /b %MANIFEST_EXIT%
