@echo off
setlocal

set "WORKSPACE=%~dp0.."
set "SRC=%WORKSPACE%\CadCapture.edu\CadCapture.m\src"
set "OUT=%WORKSPACE%\build_core"
set "EXE=%OUT%\CaptureCoreTests.exe"

if not exist "%OUT%" mkdir "%OUT%"

if "%VS90COMNTOOLS%"=="" if exist "%WORKSPACE%\..\.caa_toolchain_links\vs90\Common7\Tools\" set "VS90COMNTOOLS=%WORKSPACE%\..\.caa_toolchain_links\vs90\Common7\Tools\"
set "VSVARS=%VS90COMNTOOLS%vsvars32.bat"
if not exist "%VSVARS%" (
  echo VS2008 vsvars32.bat not found. Set VS90COMNTOOLS.
  exit /b 2
)

call "%VSVARS%" >nul
if errorlevel 1 exit /b 3

if exist "%EXE%" del /q "%EXE%"

set "OBJ1=%OUT%\CaptureCoreTestMain.obj"
set "OBJ2=%OUT%\ReconstructionPlanner.obj"
set "OBJ3=%OUT%\ReconstructionValidator.obj"
if exist "%OBJ1%" del /q "%OBJ1%"
if exist "%OBJ2%" del /q "%OBJ2%"
if exist "%OBJ3%" del /q "%OBJ3%"
if exist "%OUT%\SdkCatalog.obj" del /q "%OUT%\SdkCatalog.obj"
if exist "%OUT%\CaptureIdRegistry.obj" del /q "%OUT%\CaptureIdRegistry.obj"
if exist "%OUT%\GeometryStatusProjector.obj" del /q "%OUT%\GeometryStatusProjector.obj"
if exist "%OUT%\CaptureOutcome.obj" del /q "%OUT%\CaptureOutcome.obj"
if exist "%OUT%\CaptureEvidenceSummary.obj" del /q "%OUT%\CaptureEvidenceSummary.obj"
if exist "%OUT%\ArtifactRepository.obj" del /q "%OUT%\ArtifactRepository.obj"
if exist "%OUT%\NormalizedArtifactWriter.obj" del /q "%OUT%\NormalizedArtifactWriter.obj"
if exist "%OUT%\LegacyArtifactProjection.obj" del /q "%OUT%\LegacyArtifactProjection.obj"

cl /nologo /EHsc /I"%SRC%" /c "%WORKSPACE%\tests\CaptureCoreTestMain.cpp" /Fo"%OBJ1%"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\reconstruction\ReconstructionPlanner.cpp" /Fo"%OBJ2%"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\reconstruction\ReconstructionValidator.cpp" /Fo"%OBJ3%"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\model\SdkCatalog.cpp" /Fo"%OUT%\SdkCatalog.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\model\CaptureIdRegistry.cpp" /Fo"%OUT%\CaptureIdRegistry.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\model\GeometryStatusProjector.cpp" /Fo"%OUT%\GeometryStatusProjector.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\engine\CaptureOutcome.cpp" /Fo"%OUT%\CaptureOutcome.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\model\CaptureEvidenceSummary.cpp" /Fo"%OUT%\CaptureEvidenceSummary.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /DCADCAPTURE_TESTING /I"%SRC%" /c "%SRC%\output\ArtifactRepository.cpp" /Fo"%OUT%\ArtifactRepository.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\output\NormalizedArtifactWriter.cpp" /Fo"%OUT%\NormalizedArtifactWriter.obj"
if errorlevel 1 exit /b 4
cl /nologo /EHsc /I"%SRC%" /c "%SRC%\output\LegacyArtifactProjection.cpp" /Fo"%OUT%\LegacyArtifactProjection.obj"
if errorlevel 1 exit /b 4

link /nologo "%OBJ1%" "%OBJ2%" "%OBJ3%" "%OUT%\SdkCatalog.obj" "%OUT%\CaptureIdRegistry.obj" "%OUT%\GeometryStatusProjector.obj" "%OUT%\CaptureOutcome.obj" "%OUT%\CaptureEvidenceSummary.obj" "%OUT%\ArtifactRepository.obj" "%OUT%\NormalizedArtifactWriter.obj" "%OUT%\LegacyArtifactProjection.obj" /OUT:"%EXE%"
if errorlevel 1 exit /b 4

"%EXE%"
exit /b %errorlevel%
