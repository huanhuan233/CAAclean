@echo off
setlocal EnableExtensions

rem CATIA V5R21 / CAA RADE R21 - Windows x64 (win_b64) runner

if "%CAA_RADE_ROOT%"=="" (
  echo ERROR: CAA_RADE_ROOT is required.
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo ERROR: CAA_PREREQ_ROOT is required.
  exit /b 2
)

set "CADPARSE_PLATFORM=win_b64"
set "_MkmkOS_BitMode=64"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"
set "CADPARSE_WORKSPACE=%~dp0.."
for %%I in ("%CADPARSE_WORKSPACE%") do set "CADPARSE_WORKSPACE=%%~fI"
set "CADPARSE_EXE=%CADPARSE_WORKSPACE%\%CADPARSE_PLATFORM%\code\bin\CadParseMvp.exe"
set "MKMK_SETENV=%CAA_RADE_ROOT%\%CADPARSE_PLATFORM%\code\command\MkmkSetenv.bat"

if not exist "%MKMK_SETENV%" (
  echo ERROR: CAA RADE win_b64 environment was not found:
  echo   %MKMK_SETENV%
  exit /b 3
)

call "%MKMK_SETENV%" >nul
if errorlevel 1 exit /b 3

if not exist "%CADPARSE_EXE%" (
  echo ERROR: parser executable was not found.
  echo Run tools\build_r21_x64.bat first.
  echo Expected:
  echo   %CADPARSE_EXE%
  exit /b 4
)

set "PATH=%CADPARSE_WORKSPACE%\%CADPARSE_PLATFORM%\code\bin;%CAA_PREREQ_ROOT%\%CADPARSE_PLATFORM%\code\bin;%CAA_RADE_ROOT%\%CADPARSE_PLATFORM%\code\bin;%PATH%"

if "%CATUserSettingPath%"=="" (
  set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
)
if "%CATReferenceSettingPath%"=="" (
  if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"
)

"%CADPARSE_EXE%" %*
exit /b %errorlevel%
