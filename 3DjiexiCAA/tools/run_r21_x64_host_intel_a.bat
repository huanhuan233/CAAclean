@echo off
setlocal EnableExtensions

rem Run a win_b64 target built by build_r21_x64_host_intel_a.bat.

if "%CAA_RADE_ROOT%"=="" (
  echo ERROR: CAA_RADE_ROOT is required.
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo ERROR: CAA_PREREQ_ROOT is required.
  exit /b 2
)

set "CADPARSE_HOST_PLATFORM=intel_a"
set "CADPARSE_TARGET_PLATFORM=win_b64"
set "_MkmkOS_BitMode=64"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"

set "CADPARSE_WORKSPACE=%~dp0.."
for %%I in ("%CADPARSE_WORKSPACE%") do set "CADPARSE_WORKSPACE=%%~fI"
set "CADPARSE_EXE=%CADPARSE_WORKSPACE%\%CADPARSE_TARGET_PLATFORM%\code\bin\CadParseMvp.exe"
set "RADE_SETENV=%CAA_RADE_ROOT%\%CADPARSE_HOST_PLATFORM%\code\command\MkmkSetenv.bat"

if not exist "%RADE_SETENV%" (
  echo ERROR: Missing RADE host tool:
  echo   %RADE_SETENV%
  exit /b 3
)

call "%RADE_SETENV%" >nul
if errorlevel 1 exit /b 3
set "_MkmkOS_BitMode=64"

if not exist "%CADPARSE_EXE%" (
  echo ERROR: Parser executable not found.
  echo Run tools\build_r21_x64_host_intel_a.bat first.
  echo Expected:
  echo   %CADPARSE_EXE%
  exit /b 4
)

set "PATH=%CADPARSE_WORKSPACE%\%CADPARSE_TARGET_PLATFORM%\code\bin;%CAA_PREREQ_ROOT%\%CADPARSE_TARGET_PLATFORM%\code\bin;%PATH%"

if "%CATUserSettingPath%"=="" set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
if "%CATReferenceSettingPath%"=="" if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"

"%CADPARSE_EXE%" %*
exit /b %errorlevel%
