@echo off
setlocal
cd /d "%~dp0" || exit /b 1
for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
if /i not "%CURRENT_BRANCH%"=="main" (
    echo [BlueGuard] Please switch to main before syncing. Currently: %CURRENT_BRANCH%
    exit /b 1
)
echo [BlueGuard] Updating local main without merge commits...
git pull --ff-only origin main
if errorlevel 1 (
    echo [BlueGuard] Git pull failed. No firmware upload attempted.
    exit /b 1
)
call "%~dp0upload-firmware.bat" %*
exit /b %ERRORLEVEL%
