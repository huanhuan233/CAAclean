@echo off
setlocal

if "%CAA_RADE_ROOT%"=="" (
  echo CAA_RADE_ROOT is required, for example the CAA RADE V5R21 install root.
  exit /b 2
)
if "%CAA_PREREQ_ROOT%"=="" (
  echo CAA_PREREQ_ROOT is required, for example the CATIA V5R21 install root.
  exit /b 2
)

set "_MkmkOS_BitMode=32"
set "MkmkINSTALL_PATH=%CAA_RADE_ROOT%"
set "CADPARSE_WORKSPACE=%~dp0.."
set "CADPARSE_LOG=%CADPARSE_WORKSPACE%\build_r21.log"

call "%CAA_RADE_ROOT%\intel_a\code\command\MkmkSetenv.bat"
if errorlevel 1 exit /b 3

call "%CAA_RADE_ROOT%\intel_a\code\command\mkGetPreq.bat" -W "%CADPARSE_WORKSPACE%" -p "%CAA_PREREQ_ROOT%"
if errorlevel 1 exit /b 4

if exist "%CADPARSE_WORKSPACE%\intel_a\code\bin\CadParseMvp.exe" del /q "%CADPARSE_WORKSPACE%\intel_a\code\bin\CadParseMvp.exe"
call "%CAA_RADE_ROOT%\intel_a\code\command\mkmk.bat" -W "%CADPARSE_WORKSPACE%" CadParseMvp.edu CadParseMvp.m -jobs 1 -w > "%CADPARSE_LOG%" 2>&1
set "CADPARSE_MKMK_RESULT=%errorlevel%"
type "%CADPARSE_LOG%"

if not "%CADPARSE_MKMK_RESULT%"=="0" exit /b 5
findstr /C:"# make-ERROR" /C:"# mkmk-ERROR" /C:"# syst-ERROR" /C:": error C" /C:"fatal error" /C:"error LNK" "%CADPARSE_LOG%" >nul
if not errorlevel 1 exit /b 5
if not exist "%CADPARSE_WORKSPACE%\intel_a\code\bin\CadParseMvp.exe" exit /b 6

echo Build succeeded: %CADPARSE_WORKSPACE%\intel_a\code\bin\CadParseMvp.exe
exit /b 0
