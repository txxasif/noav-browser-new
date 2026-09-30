@echo off
REM ==============================================================================
REM  Meta Creator - Quick Launcher (Alias for Run.bat)
REM ==============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

if exist "%~dp0Run.bat" (
    call "%~dp0Run.bat"
) else (
    echo [ERROR] Run.bat not found. Please extract the full Meta Creator package.
    pause
)
