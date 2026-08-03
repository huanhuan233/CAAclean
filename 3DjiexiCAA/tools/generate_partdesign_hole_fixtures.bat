@echo off
setlocal

rem Runs the real CATIA generator and then the independent saved-file verifier.
set "FIXTURE_DIR=%~1"
if "%FIXTURE_DIR%"=="" set "FIXTURE_DIR=%~dp0..\tests\fixtures\catia_r21"

set "CSCRIPT=%SystemRoot%\SysWOW64\cscript.exe"
if not exist "%CSCRIPT%" set "CSCRIPT=%SystemRoot%\System32\cscript.exe"

"%CSCRIPT%" //nologo "%~dp0generate_partdesign_hole_fixtures.vbs" "%FIXTURE_DIR%"
if errorlevel 1 exit /b %errorlevel%

call "%~dp0verify_partdesign_hole_fixtures.bat" "%FIXTURE_DIR%"
exit /b %errorlevel%
