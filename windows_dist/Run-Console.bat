@echo off
REM ==============================================================================
REM  Meta Creator — Debug / Live Console Mode
REM
REM  Keeps the CMD terminal open so you can view all stdout/stderr logs in real
REM  time. The browser is opened only after the server actually answers an HTTP
REM  request, so a failed start shows logs here instead of a dead browser page.
REM ==============================================================================
setlocal
cd /d "%~dp0"
title Meta Creator (Live Console Debug Mode)

echo ====================================================================
echo   Meta Creator — Live Console Mode (Port 3070)
echo ====================================================================
echo.

REM 1. Verify files are properly extracted (prevent running inside zip)
if not exist "%~dp0public\index.html" (
    echo [ERROR] Application files are missing or not extracted!
    echo.
    echo It appears you are running Run-Console.bat directly from inside the ZIP file.
    echo.
    echo How to fix:
    echo   1. Close this window.
    echo   2. Right-click 'MetaCreator-Windows-Portable.zip'.
    echo   3. Click 'Extract All...' and extract to a normal folder.
    echo   4. Open the extracted folder and double-click Run-Console.bat.
    echo.
    pause
    exit /b 1
)

REM 2. Terminate any stale process occupying port 3070 before starting
netstat -ano | findstr /r /c:":3070 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [*] Port 3070 is occupied. Terminating previous instance...
    powershell -NoProfile -NonInteractive -Command "$p = Get-NetTCPConnection -LocalPort 3070 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"
    timeout /t 1 >nul
)

set "PLAYWRIGHT_BROWSERS_PATH=%~dp0_internal\ms-playwright"
set "PYTHON_BIN=%~dp0_internal\python.exe"
set "PYTHONPATH=%~dp0"
set "PATH=%~dp0bin;%~dp0_internal;%~dp0_internal\Scripts;%PATH%"

echo [*] Python Runtime:      %PYTHON_BIN%
echo [*] Playwright Browsers: %PLAYWRIGHT_BROWSERS_PATH%
echo [*] Working Directory:   %CD%
echo.

REM 3. Open the browser only once the server answers (background waiter)
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 60; $i++) { try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3070/' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { Start-Process 'http://localhost:3070'; break } } catch {}; Start-Sleep -Seconds 1 }"

if exist "%~dp0bin\node.exe" (
    "%~dp0bin\node.exe" server.js
) else (
    node server.js
)

echo.
echo [i] Server stopped. Press any key to close.
pause
