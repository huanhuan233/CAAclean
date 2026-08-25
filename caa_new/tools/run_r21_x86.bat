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
set "CADCAPTURE_EXE=%CADCAPTURE_WORKSPACE%\intel_a\code\bin\CadCapture.exe"
set "CADCAPTURE_VS90=%CADCAPTURE_WORKSPACE%\..\.caa_toolchain_links\vs90"
if "%CATUserSettingPath%"=="" set "CATUserSettingPath=%APPDATA%\DassaultSystemes\CATSettings"
if "%CATReferenceSettingPath%"=="" if exist "%CAA_PREREQ_ROOT%\CATSettings" set "CATReferenceSettingPath=%CAA_PREREQ_ROOT%\CATSettings"

call "%CAA_RADE_ROOT%\intel_a\code\command\MkmkSetenv.bat" >nul
if errorlevel 1 exit /b 3

if not exist "%CADCAPTURE_EXE%" (
  echo CadCapture.exe not found. Run build_r21_x86.bat first.
  exit /b 4
)

set "PATH=%CADCAPTURE_WORKSPACE%\intel_a\code\bin;%CAA_PREREQ_ROOT%\intel_a\code\bin;%PATH%"
if exist "%CADCAPTURE_VS90%\VC\redist\x86\Microsoft.VC90.CRT" set "PATH=%CADCAPTURE_VS90%\VC\redist\x86\Microsoft.VC90.CRT;%PATH%"

"%CADCAPTURE_EXE%" %*
exit /b %errorlevel%
