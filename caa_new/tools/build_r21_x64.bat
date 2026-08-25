@echo off
setlocal EnableExtensions

set "CADCAPTURE_HOST_PLATFORM=intel_a"
set "CADCAPTURE_TARGET_PLATFORM=win_b64"
set "CADCAPTURE_WORKSPACE=%~dp0.."
for %%I in ("%CADCAPTURE_WORKSPACE%") do set "CADCAPTURE_WORKSPACE=%%~fI"

if "%CAA_RADE_ROOT%"=="" if exist "%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\rade21\intel_a\code\command\MkmkSetenv.bat" set "CAA_RADE_ROOT=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\rade21"
if "%CAA_PREREQ_ROOT%"=="" if exist "%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\catia21\win_b64\code\bin\CNEXT.exe" set "CAA_PREREQ_ROOT=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\catia21"

if "%CAA_RADE_ROOT%"=="" (
  echo CAA_RADE_ROOT is required.
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo CAA_PREREQ_ROOT is required.
  exit /b 2
)

set "_MkmkOS_BitMode=64"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"
set "CADCAPTURE_LOG=%CADCAPTURE_WORKSPACE%\build_r21_x64.log"
set "CADCAPTURE_EXE=%CADCAPTURE_WORKSPACE%\%CADCAPTURE_TARGET_PLATFORM%\code\bin\CadCapture.exe"
set "RADE_CMD=%CAA_RADE_ROOT%\%CADCAPTURE_HOST_PLATFORM%\code\command"
set "CADCAPTURE_VS90=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\vs90"

if "%CATUserSettingPath%"=="" set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
if "%CATReferenceSettingPath%"=="" if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"
if "%RADECATSettingPath%"=="" if exist "%CATUserSettingPath%\RADE\RADELicensing.xml" set "RADECATSettingPath=%CATUserSettingPath%\RADE"
if "%RADECATSettingPath%"=="" set "RADECATSettingPath=%CATUserSettingPath%"

if not exist "%RADE_CMD%\MkmkSetenv.bat" exit /b 3
if not exist "%RADE_CMD%\mkGetPreq.bat" exit /b 3
if not exist "%RADE_CMD%\mkmk.bat" exit /b 3
if not exist "%CAA_PREREQ_ROOT%\%CADCAPTURE_TARGET_PLATFORM%\code\bin\CNEXT.exe" exit /b 3

call "%RADE_CMD%\MkmkSetenv.bat"
if errorlevel 1 exit /b 4
set "_MkmkOS_BitMode=64"

if "%VS90COMNTOOLS%"=="" if exist "%CADCAPTURE_VS90%\Common7\Tools\vsvars32.bat" set "VS90COMNTOOLS=%CADCAPTURE_VS90%\Common7\Tools\"
if "%VS90COMNTOOLS%"=="" exit /b 5
for %%I in ("%VS90COMNTOOLS%..\..\VC") do set "VC_ROOT=%%~fI"
set "VCVARSALL=%VC_ROOT%\vcvarsall.bat"
set "VC_ARCH="
if exist "%VC_ROOT%\bin\amd64\cl.exe" set "VC_ARCH=amd64"
if not defined VC_ARCH if exist "%VC_ROOT%\bin\x86_amd64\cl.exe" set "VC_ARCH=x86_amd64"
if not defined VC_ARCH exit /b 5
call "%VCVARSALL%" %VC_ARCH%
if errorlevel 1 exit /b 5

call "%RADE_CMD%\mkGetPreq.bat" -W "%CADCAPTURE_WORKSPACE%" -p "%CAA_PREREQ_ROOT%"
if errorlevel 1 exit /b 6

if exist "%CADCAPTURE_EXE%" del /q "%CADCAPTURE_EXE%"

call "%RADE_CMD%\mkmk.bat" -W "%CADCAPTURE_WORKSPACE%" CadCapture.edu CadCapture.m -jobs 1 -w > "%CADCAPTURE_LOG%" 2>&1
set "CADCAPTURE_MKMK_RESULT=%errorlevel%"
type "%CADCAPTURE_LOG%"

if not "%CADCAPTURE_MKMK_RESULT%"=="0" exit /b 7
findstr /C:"# make-ERROR" /C:"# mkmk-ERROR" /C:"# syst-ERROR" /C:"error C" /C:"fatal error" /C:"error LNK" /C:"LNK1112" "%CADCAPTURE_LOG%" >nul
if not errorlevel 1 exit /b 7
if not exist "%CADCAPTURE_EXE%" exit /b 8

echo Build succeeded
echo %CADCAPTURE_EXE%
exit /b 0
