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
set "CADCAPTURE_EXE=%CADCAPTURE_WORKSPACE%\%CADCAPTURE_TARGET_PLATFORM%\code\bin\CadCapture.exe"
set "RADE_CMD=%CAA_RADE_ROOT%\%CADCAPTURE_HOST_PLATFORM%\code\command"
set "CADCAPTURE_VS90=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\vs90"

if "%CATUserSettingPath%"=="" set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
if "%CATReferenceSettingPath%"=="" if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"
if "%RADECATSettingPath%"=="" if exist "%CATUserSettingPath%\RADE\RADELicensing.xml" set "RADECATSettingPath=%CATUserSettingPath%\RADE"
if "%RADECATSettingPath%"=="" set "RADECATSettingPath=%CATUserSettingPath%"

call "%RADE_CMD%\MkmkSetenv.bat" >nul
if errorlevel 1 exit /b 3
set "_MkmkOS_BitMode=64"

if not exist "%CADCAPTURE_EXE%" (
  echo CadCapture.exe not found. Run build_r21_x64.bat first.
  exit /b 4
)

set "PATH=%CADCAPTURE_WORKSPACE%\%CADCAPTURE_TARGET_PLATFORM%\code\bin;%CAA_PREREQ_ROOT%\%CADCAPTURE_TARGET_PLATFORM%\code\bin;%CAA_RADE_ROOT%\intel_a\code\bin;%PATH%"
if exist "%CADCAPTURE_VS90%\VC\redist\amd64\Microsoft.VC90.CRT" set "PATH=%CADCAPTURE_VS90%\VC\redist\amd64\Microsoft.VC90.CRT;%PATH%"

"%CADCAPTURE_EXE%" %*
exit /b %errorlevel%
