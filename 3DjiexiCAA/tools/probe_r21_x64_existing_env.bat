@echo off
setlocal EnableExtensions

echo ============================================================
echo CATIA V5R21 / CAA RADE R21 existing-environment probe
echo Host tool expected: RADE\intel_a
echo Target expected:    CATIA/CAA\win_b64
echo ============================================================
echo.

if "%CAA_RADE_ROOT%"=="" (
  echo [FAIL] CAA_RADE_ROOT is not set.
  echo        Example: set "CAA_RADE_ROOT=D:\DassaultSystemes\T21"
  set "PROBE_FAILED=1"
) else (
  echo CAA_RADE_ROOT=%CAA_RADE_ROOT%
)

if "%CAA_PREREQ_ROOT%"=="" (
  echo [FAIL] CAA_PREREQ_ROOT is not set.
  echo        Example: set "CAA_PREREQ_ROOT=D:\DassaultSystemes\B21"
  set "PROBE_FAILED=1"
) else (
  echo CAA_PREREQ_ROOT=%CAA_PREREQ_ROOT%
)
echo.

if defined PROBE_FAILED exit /b 2

set "RADE_CMD=%CAA_RADE_ROOT%\intel_a\code\command"
set "CATIA_X64=%CAA_PREREQ_ROOT%\win_b64"

if exist "%RADE_CMD%\MkmkSetenv.bat" (
  echo [PASS] RADE host MkmkSetenv: %RADE_CMD%\MkmkSetenv.bat
) else (
  echo [FAIL] Missing RADE host MkmkSetenv:
  echo        %RADE_CMD%\MkmkSetenv.bat
  set "PROBE_FAILED=1"
)

if exist "%RADE_CMD%\mkGetPreq.bat" (
  echo [PASS] RADE host mkGetPreq:   %RADE_CMD%\mkGetPreq.bat
) else (
  echo [FAIL] Missing RADE host mkGetPreq:
  echo        %RADE_CMD%\mkGetPreq.bat
  set "PROBE_FAILED=1"
)

if exist "%RADE_CMD%\mkmk.bat" (
  echo [PASS] RADE host mkmk:        %RADE_CMD%\mkmk.bat
) else (
  echo [FAIL] Missing RADE host mkmk:
  echo        %RADE_CMD%\mkmk.bat
  set "PROBE_FAILED=1"
)

if exist "%CATIA_X64%\code\bin\CNEXT.exe" (
  echo [PASS] CATIA x64 runtime:     %CATIA_X64%\code\bin\CNEXT.exe
) else (
  echo [FAIL] Missing CATIA x64 runtime:
  echo        %CATIA_X64%\code\bin\CNEXT.exe
  set "PROBE_FAILED=1"
)

if exist "%CATIA_X64%\code\lib" (
  echo [PASS] CATIA x64 libraries:   %CATIA_X64%\code\lib
) else (
  echo [FAIL] Missing CATIA x64 library directory:
  echo        %CATIA_X64%\code\lib
  set "PROBE_FAILED=1"
)

echo.
echo === Visual Studio 2008 x64 compiler ===
if "%VS90COMNTOOLS%"=="" (
  if exist "%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\vsvars32.bat" (
    set "VS90COMNTOOLS=%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\"
  )
)
if "%VS90COMNTOOLS%"=="" (
  echo [FAIL] VS90COMNTOOLS is not set and VS2008 was not found at the default path.
  set "PROBE_FAILED=1"
  goto :probe_end
)

for %%I in ("%VS90COMNTOOLS%..\..\VC") do set "VC_ROOT=%%~fI"
set "VCVARSALL=%VC_ROOT%\vcvarsall.bat"

if not exist "%VCVARSALL%" (
  echo [FAIL] Missing VS2008 vcvarsall.bat:
  echo        %VCVARSALL%
  set "PROBE_FAILED=1"
  goto :probe_end
)

set "VC_ARCH="
if exist "%VC_ROOT%\bin\amd64\cl.exe" set "VC_ARCH=amd64"
if not defined VC_ARCH if exist "%VC_ROOT%\bin\x86_amd64\cl.exe" set "VC_ARCH=x86_amd64"

if not defined VC_ARCH (
  echo [FAIL] VS2008 x64 compiler binaries are not installed.
  echo        Looked for:
  echo        %VC_ROOT%\bin\amd64\cl.exe
  echo        %VC_ROOT%\bin\x86_amd64\cl.exe
  set "PROBE_FAILED=1"
  goto :probe_end
)

echo [PASS] VS2008 x64 compiler mode: %VC_ARCH%
echo        VC root: %VC_ROOT%

:probe_end
echo.
if defined PROBE_FAILED (
  echo ============================================================
  echo RESULT: NOT READY for a complete win_b64 CAA build.
  echo No script can replace a missing prerequisite or x64 compiler.
  echo ============================================================
  exit /b 1
)

echo ============================================================
echo RESULT: BASIC FILE LAYOUT IS READY.
echo Next run build_r21_x64_host_intel_a.bat.
echo mkGetPreq/mkmk will perform the final CAA framework check.
echo ============================================================
exit /b 0
