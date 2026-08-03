@echo off
setlocal

if "%CAA_RADE_ROOT%"=="" (
  echo CAA_RADE_ROOT is required.
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo CAA_PREREQ_ROOT is required.
  exit /b 2
)

set "_MkmkOS_BitMode=32"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"
set "CADPARSE_WORKSPACE=%~dp0.."
set "CADPARSE_EXE=%CADPARSE_WORKSPACE%\intel_a\code\bin\CadParseMvp.exe"

call "%CAA_RADE_ROOT%\intel_a\code\command\MkmkSetenv.bat" >nul
if errorlevel 1 exit /b 3
if not exist "%CADPARSE_EXE%" (
  echo Parser executable not found. Run build_r21_x86.bat first.
  exit /b 4
)

set "PATH=%CADPARSE_WORKSPACE%\intel_a\code\bin;%CAA_PREREQ_ROOT%\intel_a\code\bin;%PATH%"
if "%CATUserSettingPath%"=="" set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
if "%CATReferenceSettingPath%"=="" if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"

"%CADPARSE_EXE%" %*
exit /b %errorlevel%
