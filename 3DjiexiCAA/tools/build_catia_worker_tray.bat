@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo ERROR: .NET Framework C# compiler csc.exe was not found.
  exit /b 2
)

"%CSC%" ^
  /nologo ^
  /target:winexe ^
  /platform:x64 ^
  /out:"%SCRIPT_DIR%CatiaWorkerTray.exe" ^
  /reference:System.dll ^
  /reference:System.Drawing.dll ^
  /reference:System.Windows.Forms.dll ^
  "%SCRIPT_DIR%CatiaWorkerTray.cs"

exit /b %ERRORLEVEL%
