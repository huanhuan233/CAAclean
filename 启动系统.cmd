@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start_system.ps1" %*
set "CAD_START_EXIT=%ERRORLEVEL%"
echo.
if not "%~1"=="-Check" pause
exit /b %CAD_START_EXIT%
