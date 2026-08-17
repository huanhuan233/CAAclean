@echo off
setlocal EnableExtensions

rem CATIA V5R21 / CAA RADE R21 - Windows x64 (win_b64) build
rem Keep the existing build_r21_x86.bat for intel_a machines.

if "%CAA_RADE_ROOT%"=="" (
  echo ERROR: CAA_RADE_ROOT is required.
  echo Example: set "CAA_RADE_ROOT=D:\CATIA\Rade21"
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo ERROR: CAA_PREREQ_ROOT is required.
  echo Example: set "CAA_PREREQ_ROOT=D:\CATIA"
  exit /b 2
)

set "CADPARSE_PLATFORM=win_b64"
set "_MkmkOS_BitMode=64"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"
set "CADPARSE_WORKSPACE=%~dp0.."
for %%I in ("%CADPARSE_WORKSPACE%") do set "CADPARSE_WORKSPACE=%%~fI"
set "CADPARSE_LOG=%CADPARSE_WORKSPACE%\build_r21_x64.log"
set "CADPARSE_EXE=%CADPARSE_WORKSPACE%\%CADPARSE_PLATFORM%\code\bin\CadParseMvp.exe"

set "MKMK_SETENV=%CAA_RADE_ROOT%\%CADPARSE_PLATFORM%\code\command\MkmkSetenv.bat"
set "MKMK_GETPREQ=%CAA_RADE_ROOT%\%CADPARSE_PLATFORM%\code\command\mkGetPreq.bat"
set "MKMK_BUILD=%CAA_RADE_ROOT%\%CADPARSE_PLATFORM%\code\command\mkmk.bat"

if not exist "%MKMK_SETENV%" (
  echo ERROR: win_b64 CAA RADE environment was not found:
  echo   %MKMK_SETENV%
  exit /b 3
)
if not exist "%MKMK_GETPREQ%" (
  echo ERROR: mkGetPreq.bat was not found:
  echo   %MKMK_GETPREQ%
  exit /b 3
)
if not exist "%MKMK_BUILD%" (
  echo ERROR: mkmk.bat was not found:
  echo   %MKMK_BUILD%
  exit /b 3
)
if not exist "%CAA_PREREQ_ROOT%\%CADPARSE_PLATFORM%\code\bin" (
  echo ERROR: CATIA win_b64 prerequisite directory was not found:
  echo   %CAA_PREREQ_ROOT%\%CADPARSE_PLATFORM%\code\bin
  exit /b 3
)

rem Locate the Visual Studio 2008 x64 compiler environment.
if "%VS90COMNTOOLS%"=="" (
  if exist "%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\vsvars32.bat" (
    set "VS90COMNTOOLS=%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\"
  )
)
if "%VS90COMNTOOLS%"=="" (
  echo ERROR: VS90COMNTOOLS is not set. Install Visual Studio 2008 SP1.
  exit /b 4
)
for %%I in ("%VS90COMNTOOLS%..\..\VC\vcvarsall.bat") do set "VCVARSALL=%%~fI"
if not exist "%VCVARSALL%" (
  echo ERROR: Visual Studio 2008 vcvarsall.bat was not found:
  echo   %VCVARSALL%
  exit /b 4
)

echo === Visual Studio 2008 x64 environment ===
call "%VCVARSALL%" amd64
if errorlevel 1 (
  echo ERROR: VS2008 x64 compiler environment could not be initialized.
  echo Re-run VS2008 setup and install Visual C++ x64 Compilers and Tools.
  exit /b 4
)
where cl >nul 2>&1
if errorlevel 1 (
  echo ERROR: cl.exe is unavailable after vcvarsall amd64.
  exit /b 4
)

echo === CAA RADE win_b64 environment ===
call "%MKMK_SETENV%"
if errorlevel 1 exit /b 5

echo === Resolve CAA prerequisites ===
call "%MKMK_GETPREQ%" -W "%CADPARSE_WORKSPACE%" -p "%CAA_PREREQ_ROOT%"
if errorlevel 1 exit /b 6

rem Embed source revision/build time exactly as the existing x86 script does.
set "CADPARSE_GIT_COMMIT=unknown"
for /f "usebackq delims=" %%G in (`git -C "%CADPARSE_WORKSPACE%" rev-parse HEAD 2^>nul`) do set "CADPARSE_GIT_COMMIT=%%G"
set "CADPARSE_BUILD_TIMESTAMP_UTC=unknown"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')"`) do set "CADPARSE_BUILD_TIMESTAMP_UTC=%%T"
set "CL=/DCAD_PARSE_GIT_COMMIT=\"%CADPARSE_GIT_COMMIT%\" /DCAD_PARSE_BUILD_TIMESTAMP_UTC=\"%CADPARSE_BUILD_TIMESTAMP_UTC%\" %CL%"

rem Remove stale x64 output so an old executable cannot be mistaken for a successful build.
if exist "%CADPARSE_EXE%" del /q "%CADPARSE_EXE%"
if exist "%CADPARSE_WORKSPACE%\CadParseMvp.edu\CadParseMvp.m\Objects\%CADPARSE_PLATFORM%\CadParseBatch.obj" (
  del /q "%CADPARSE_WORKSPACE%\CadParseMvp.edu\CadParseMvp.m\Objects\%CADPARSE_PLATFORM%\CadParseBatch.obj"
)

echo === Build CadParseMvp for win_b64 ===
call "%MKMK_BUILD%" -W "%CADPARSE_WORKSPACE%" CadParseMvp.edu CadParseMvp.m -jobs 1 -w > "%CADPARSE_LOG%" 2>&1
set "CADPARSE_MKMK_RESULT=%errorlevel%"
type "%CADPARSE_LOG%"

if not "%CADPARSE_MKMK_RESULT%"=="0" (
  echo ERROR: mkmk returned %CADPARSE_MKMK_RESULT%.
  echo Log: %CADPARSE_LOG%
  exit /b 7
)

findstr /C:"# make-ERROR" /C:"# mkmk-ERROR" /C:"# syst-ERROR" /C:": error C" /C:"fatal error" /C:"error LNK" "%CADPARSE_LOG%" >nul
if not errorlevel 1 (
  echo ERROR: build log contains a compiler/linker/mkmk error.
  echo Log: %CADPARSE_LOG%
  exit /b 7
)

if not exist "%CADPARSE_EXE%" (
  echo ERROR: x64 executable was not generated:
  echo   %CADPARSE_EXE%
  exit /b 8
)

rem Verify the PE machine type when dumpbin is available.
where dumpbin >nul 2>&1
if not errorlevel 1 (
  dumpbin /headers "%CADPARSE_EXE%" | findstr /I /C:"machine (x64)" /C:"8664 machine" >nul
  if errorlevel 1 (
    echo ERROR: generated executable does not appear to be x64.
    exit /b 9
  )
)

echo.
echo Build succeeded:
echo   %CADPARSE_EXE%
echo Log:
echo   %CADPARSE_LOG%
exit /b 0
