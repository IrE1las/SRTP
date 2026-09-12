@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1"
if errorlevel 1 (
    echo.
    echo Startup failed. See the errors above or the logs in the .runtime folder.
    pause
    exit /b 1
)
echo.
echo Close this window does not stop the services. Run the stop script to stop them.
echo.
pause
