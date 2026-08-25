@echo off
setlocal

set "CADCAPTURE_WORKSPACE=%~dp0.."
if "%CAA_RADE_ROOT%"=="" if exist "%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\rade21\intel_a\code\command\MkmkSetenv.bat" set "CAA_RADE_ROOT=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\rade21"
if "%CAA_PREREQ_ROOT%"=="" if exist "%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\catia21\intel_a\code\bin" set "CAA_PREREQ_ROOT=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\catia21"

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
set "CADCAPTURE_LOG=%CADCAPTURE_WORKSPACE%\build_r21.log"
set "CADCAPTURE_EXE=%CADCAPTURE_WORKSPACE%\intel_a\code\bin\CadCapture.exe"
if "%CATUserSettingPath%"=="" set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
if "%CATReferenceSettingPath%"=="" if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"
if "%RADECATSettingPath%"=="" if exist "%CATUserSettingPath%\RADE\RADELicensing.xml" set "RADECATSettingPath=%CATUserSettingPath%\RADE"
if "%RADECATSettingPath%"=="" set "RADECATSettingPath=%CATUserSettingPath%"

call "%CAA_RADE_ROOT%\intel_a\code\command\MkmkSetenv.bat"
if errorlevel 1 exit /b 3

call "%CAA_RADE_ROOT%\intel_a\code\command\mkGetPreq.bat" -W "%CADCAPTURE_WORKSPACE%" -p "%CAA_PREREQ_ROOT%"
if errorlevel 1 exit /b 4

if exist "%CADCAPTURE_EXE%" del /q "%CADCAPTURE_EXE%"

call "%CAA_RADE_ROOT%\intel_a\code\command\mkmk.bat" -W "%CADCAPTURE_WORKSPACE%" CadCapture.edu CadCapture.m -jobs 1 -w > "%CADCAPTURE_LOG%" 2>&1
set "CADCAPTURE_MKMK_RESULT=%errorlevel%"
type "%CADCAPTURE_LOG%"

if not "%CADCAPTURE_MKMK_RESULT%"=="0" exit /b 5
findstr /C:"# make-ERROR" /C:"# mkmk-ERROR" /C:"error C" /C:"fatal error" /C:"error LNK" "%CADCAPTURE_LOG%" >nul
if not errorlevel 1 exit /b 5
if not exist "%CADCAPTURE_EXE%" exit /b 6

echo Build succeeded
echo %CADCAPTURE_EXE%
exit /b 0
