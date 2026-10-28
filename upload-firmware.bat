@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || exit /b 1
set "BG_BRANCH="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "BG_BRANCH=%%B"
if /i not "%BG_BRANCH%"=="main" (
    echo [BlueGuard] Wrong Git branch: %BG_BRANCH%. Switch to main first.
    popd
    exit /b 1
)
echo [BlueGuard] Pulling the latest main safely...
git pull --ff-only origin main
if errorlevel 1 (
    echo [BlueGuard] Git pull failed. No firmware uploaded.
    popd
    exit /b 1
)
echo [BlueGuard] Preparing manifest-driven upload and COM selection...
py -3 tools\deploy_firmware.py %*
set "BG_RESULT=%ERRORLEVEL%"
if not "%BG_RESULT%"=="0" echo [BlueGuard] Upload stopped. Fix the issue, then rerun this BAT file.
popd
exit /b %BG_RESULT%
