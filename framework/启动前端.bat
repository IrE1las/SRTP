@echo off
chcp 65001 >nul
echo ============================================
echo   启动前端 (Vite, 端口 5173)
echo   浏览器打开 http://localhost:5173
echo ============================================
cd /d "%~dp0frontend"
call npm run dev
pause
