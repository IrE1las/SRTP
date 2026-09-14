@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\launch.ps1" %*
set "SRTP_EXIT=%ERRORLEVEL%"
echo.
if not "%SRTP_EXIT%"=="0" echo Startup failed. See the errors above and .runtime\launch-v2.log.
if "%SRTP_EXIT%"=="0" echo Services keep running after this window closes. Use the stop BAT to stop this checkout.
if not "%SRTP_NO_PAUSE%"=="1" pause
exit /b %SRTP_EXIT%
