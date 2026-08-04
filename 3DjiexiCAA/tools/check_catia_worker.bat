@echo off
setlocal
rem 用途：验证 Worker 是否可达；若配置了令牌，请先设置 CATIA_WORKER_TOKEN。
if "%CATIA_WORKER_TOKEN%"=="" (
  curl.exe --fail --silent --show-error http://127.0.0.1:5182/health
) else (
  curl.exe --fail --silent --show-error -H "Authorization: Bearer %CATIA_WORKER_TOKEN%" http://127.0.0.1:5182/health
)
exit /b %ERRORLEVEL%
