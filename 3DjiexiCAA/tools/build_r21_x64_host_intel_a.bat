@echo off
setlocal EnableExtensions

rem ============================================================
rem CATIA V5R21 CAA x64 target build
rem Host RADE tools: intel_a (normal for an older R21 RADE install)
rem Target/runtime:  win_b64
rem ============================================================

if "%CAA_RADE_ROOT%"=="" (
  echo ERROR: CAA_RADE_ROOT is required.
  echo Example: set "CAA_RADE_ROOT=D:\DassaultSystemes\T21"
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo ERROR: CAA_PREREQ_ROOT is required.
  echo Example: set "CAA_PREREQ_ROOT=D:\DassaultSystemes\B21"
  exit /b 2
)

set "CADPARSE_HOST_PLATFORM=intel_a"
set "CADPARSE_TARGET_PLATFORM=win_b64"
set "_MkmkOS_BitMode=64"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"

set "CADPARSE_WORKSPACE=%~dp0.."
for %%I in ("%CADPARSE_WORKSPACE%") do set "CADPARSE_WORKSPACE=%%~fI"
set "CADPARSE_LOG=%CADPARSE_WORKSPACE%\build_r21_x64.log"
set "CADPARSE_EXE=%CADPARSE_WORKSPACE%\%CADPARSE_TARGET_PLATFORM%\code\bin\CadParseMvp.exe"
set "RADE_CMD=%CAA_RADE_ROOT%\%CADPARSE_HOST_PLATFORM%\code\command"

if not exist "%RADE_CMD%\MkmkSetenv.bat" (
  echo ERROR: Missing RADE host tool:
  echo   %RADE_CMD%\MkmkSetenv.bat
  exit /b 3
)
if not exist "%RADE_CMD%\mkGetPreq.bat" (
  echo ERROR: Missing RADE host tool:
  echo   %RADE_CMD%\mkGetPreq.bat
  exit /b 3
)
if not exist "%RADE_CMD%\mkmk.bat" (
  echo ERROR: Missing RADE host tool:
  echo   %RADE_CMD%\mkmk.bat
  exit /b 3
)
if not exist "%CAA_PREREQ_ROOT%\%CADPARSE_TARGET_PLATFORM%\code\bin\CNEXT.exe" (
  echo ERROR: Missing 64-bit CATIA runtime:
  echo   %CAA_PREREQ_ROOT%\%CADPARSE_TARGET_PLATFORM%\code\bin\CNEXT.exe
  exit /b 3
)

echo === Initialize R21 RADE host tools ===
set "_MkmkOS_BitMode=64"
call "%RADE_CMD%\MkmkSetenv.bat"
if errorlevel 1 exit /b 4
rem Some old setup scripts rewrite environment variables; force target again.
set "_MkmkOS_BitMode=64"

echo === Ensure VS2008 x64 compiler is selected ===
if "%VS90COMNTOOLS%"=="" (
  if exist "%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\vsvars32.bat" (
    set "VS90COMNTOOLS=%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\"
  )
)
if "%VS90COMNTOOLS%"=="" (
  echo ERROR: VS2008 was not found.
  exit /b 5
)
for %%I in ("%VS90COMNTOOLS%..\..\VC") do set "VC_ROOT=%%~fI"
set "VCVARSALL=%VC_ROOT%\vcvarsall.bat"
set "VC_ARCH="
if exist "%VC_ROOT%\bin\amd64\cl.exe" set "VC_ARCH=amd64"
if not defined VC_ARCH if exist "%VC_ROOT%\bin\x86_amd64\cl.exe" set "VC_ARCH=x86_amd64"
if not defined VC_ARCH (
  echo ERROR: VS2008 x64 compiler is not installed.
  exit /b 5
)
call "%VCVARSALL%" %VC_ARCH%
if errorlevel 1 exit /b 5

echo === Resolve 64-bit CAA/CATIA prerequisites ===
call "%RADE_CMD%\mkGetPreq.bat" -W "%CADPARSE_WORKSPACE%" -p "%CAA_PREREQ_ROOT%"
if errorlevel 1 (
  echo ERROR: mkGetPreq failed.
  echo This usually means the matching R21 CAA API frameworks are not present
  echo in CAA_PREREQ_ROOT, even if 64-bit CATIA itself can start.
  exit /b 6
)

rem Embed exact source revision and UTC build time.
set "CADPARSE_GIT_COMMIT=unknown"
for /f "usebackq delims=" %%G in (`git -C "%CADPARSE_WORKSPACE%" rev-parse HEAD 2^>nul`) do set "CADPARSE_GIT_COMMIT=%%G"
set "CADPARSE_BUILD_TIMESTAMP_UTC=unknown"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')"`) do set "CADPARSE_BUILD_TIMESTAMP_UTC=%%T"
set "CL=/DCAD_PARSE_GIT_COMMIT=\"%CADPARSE_GIT_COMMIT%\" /DCAD_PARSE_BUILD_TIMESTAMP_UTC=\"%CADPARSE_BUILD_TIMESTAMP_UTC%\" %CL%"

rem Never accept a stale executable as a successful x64 build.
if exist "%CADPARSE_EXE%" del /q "%CADPARSE_EXE%"
if exist "%CADPARSE_WORKSPACE%\CadParseMvp.edu\CadParseMvp.m\Objects\%CADPARSE_TARGET_PLATFORM%\CadParseBatch.obj" (
  del /q "%CADPARSE_WORKSPACE%\CadParseMvp.edu\CadParseMvp.m\Objects\%CADPARSE_TARGET_PLATFORM%\CadParseBatch.obj"
)

echo === Build CadParseMvp target win_b64 ===
call "%RADE_CMD%\mkmk.bat" -W "%CADPARSE_WORKSPACE%" CadParseMvp.edu CadParseMvp.m -jobs 1 -w > "%CADPARSE_LOG%" 2>&1
set "CADPARSE_MKMK_RESULT=%errorlevel%"
type "%CADPARSE_LOG%"

if not "%CADPARSE_MKMK_RESULT%"=="0" (
  echo ERROR: mkmk returned %CADPARSE_MKMK_RESULT%.
  echo Log: %CADPARSE_LOG%
  exit /b 7
)

findstr /C:"# make-ERROR" /C:"# mkmk-ERROR" /C:"# syst-ERROR" /C:": error C" /C:"fatal error" /C:"error LNK" /C:"LNK1112" "%CADPARSE_LOG%" >nul
if not errorlevel 1 (
  echo ERROR: build log contains a compiler, linker, architecture, or mkmk error.
  echo Log: %CADPARSE_LOG%
  exit /b 7
)

if not exist "%CADPARSE_EXE%" (
  echo ERROR: x64 executable was not generated:
  echo   %CADPARSE_EXE%
  exit /b 8
)

where dumpbin >nul 2>&1
if not errorlevel 1 (
  dumpbin /headers "%CADPARSE_EXE%" | findstr /I /C:"machine (x64)" /C:"8664 machine" >nul
  if errorlevel 1 (
    echo ERROR: the generated executable does not appear to be x64.
    exit /b 9
  )
)

echo.
echo Build succeeded:
echo   %CADPARSE_EXE%
echo Log:
echo   %CADPARSE_LOG%
exit /b 0
