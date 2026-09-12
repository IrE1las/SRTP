@echo off
chcp 65001 >nul
echo ============================================
echo   启动后端 (FastAPI, 端口 8000)
echo ============================================
cd /d "%~dp0backend"
set PYTHONDONTWRITEBYTECODE=1
set TEMP=%~dp0..\.runtime\tmp
set TMP=%TEMP%
"%~dp0..\.runtime\venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
