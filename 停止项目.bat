@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
set "SRTP_EXIT=%ERRORLEVEL%"
echo.
if not "%SRTP_EXIT%"=="0" echo Stop failed. See the errors above.
if "%SRTP_EXIT%"=="0" echo Stop command completed.
if not "%SRTP_NO_PAUSE%"=="1" pause
exit /b %SRTP_EXIT%
