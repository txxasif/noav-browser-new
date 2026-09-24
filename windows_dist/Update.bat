@echo off
REM ==============================================================================
REM  Meta Creator - Safe In-Place Updater
REM  The PowerShell implementation owns archive extraction and data safety.
REM ==============================================================================
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0Update.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Meta Creator update failed with exit code %RC%.
)
exit /b %RC%
