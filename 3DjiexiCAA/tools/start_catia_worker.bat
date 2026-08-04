@echo off
setlocal
rem 用途：在已激活的 3dcad Conda 环境中启动独立 CATIA Worker，不启动 Web 数据库。
set "REPO_ROOT=%~dp0..\.."
pushd "%REPO_ROOT%\backend"
python -m uvicorn app.catia_worker.server:app --host 127.0.0.1 --port 5182
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
