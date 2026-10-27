@echo off
setlocal
cd /d "%~dp0" || exit /b 1
py -3 tools\deploy_firmware.py %*
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" echo [BlueGuard] Upload failed. Device may contain a partial upload; rerun safely after resolving the error.
exit /b %EXITCODE%
