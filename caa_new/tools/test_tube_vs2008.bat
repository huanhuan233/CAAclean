@echo off
setlocal
set "WORKSPACE=%~dp0.."
set "SRC=%WORKSPACE%\CadCapture.edu\CadCapture.m\src"
if "%VS90COMNTOOLS%"=="" set "VS90COMNTOOLS=C:\Program Files (x86)\Microsoft Visual Studio 9.0\Common7\Tools\"
call "%VS90COMNTOOLS%vsvars32.bat" >nul
if errorlevel 1 exit /b 2
if not exist "%WORKSPACE%\build_core" mkdir "%WORKSPACE%\build_core"
pushd "%WORKSPACE%\build_core"
cl /nologo /EHsc /I"%SRC%" /c "%WORKSPACE%\tests\TubePathTests.cpp" /FoTubePathTests.obj
if errorlevel 1 (popd & exit /b 3)
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\model\TubePath.cpp" /FoTubePath.obj
if errorlevel 1 (popd & exit /b 3)
link /nologo TubePathTests.obj TubePath.obj /OUT:TubePathTests.exe
if errorlevel 1 (popd & exit /b 3)
TubePathTests.exe
set "RESULT=%errorlevel%"
popd
exit /b %RESULT%
