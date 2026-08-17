@echo off
setlocal EnableExtensions

rem Optional: compile and run the API-independent core tests as x64 with VS2008.

if "%VS90COMNTOOLS%"=="" (
  if exist "%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\vsvars32.bat" (
    set "VS90COMNTOOLS=%ProgramFiles(x86)%\Microsoft Visual Studio 9.0\Common7\Tools\"
  )
)
if "%VS90COMNTOOLS%"=="" (
  echo ERROR: VS90COMNTOOLS is required.
  exit /b 2
)

for %%I in ("%VS90COMNTOOLS%..\..\VC\vcvarsall.bat") do set "VCVARSALL=%%~fI"
if not exist "%VCVARSALL%" (
  echo ERROR: vcvarsall.bat was not found: %VCVARSALL%
  exit /b 2
)

call "%VCVARSALL%" amd64
if errorlevel 1 (
  echo ERROR: VS2008 x64 compiler tools are not installed.
  exit /b 3
)

set "CADPARSE_ROOT=%~dp0.."
for %%I in ("%CADPARSE_ROOT%") do set "CADPARSE_ROOT=%%~fI"
set "CADPARSE_SRC=%CADPARSE_ROOT%\CadParseMvp.edu\CadParseMvp.m\src"
set "CADPARSE_BUILD=%CADPARSE_ROOT%\build_core_x64"

if not exist "%CADPARSE_BUILD%" mkdir "%CADPARSE_BUILD%"

cl /nologo /EHsc /W4 /D_CRT_SECURE_NO_WARNINGS /I"%CADPARSE_SRC%" /c "%CADPARSE_SRC%\CadParseCore.cpp" /Fo"%CADPARSE_BUILD%\CadParseCore.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /W4 /D_CRT_SECURE_NO_WARNINGS /I"%CADPARSE_SRC%" /c "%CADPARSE_SRC%\CadParseIR.cpp" /Fo"%CADPARSE_BUILD%\CadParseIR.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /W4 /D_CRT_SECURE_NO_WARNINGS /I"%CADPARSE_SRC%" /c "%CADPARSE_SRC%\CadParseSelfTests.cpp" /Fo"%CADPARSE_BUILD%\CadParseSelfTests.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /W4 /D_CRT_SECURE_NO_WARNINGS /I"%CADPARSE_SRC%" /c "%CADPARSE_ROOT%\tests\CadParseCoreTestMain.cpp" /Fo"%CADPARSE_BUILD%\CadParseCoreTestMain.obj"
if errorlevel 1 exit /b 4

link /nologo /MACHINE:X64 ^
  "%CADPARSE_BUILD%\CadParseCore.obj" ^
  "%CADPARSE_BUILD%\CadParseIR.obj" ^
  "%CADPARSE_BUILD%\CadParseSelfTests.obj" ^
  "%CADPARSE_BUILD%\CadParseCoreTestMain.obj" ^
  /OUT:"%CADPARSE_BUILD%\CadParseCoreTests.exe"
if errorlevel 1 exit /b 5

pushd "%CADPARSE_BUILD%"
CadParseCoreTests.exe
set "CADPARSE_RESULT=%errorlevel%"
popd
exit /b %CADPARSE_RESULT%
