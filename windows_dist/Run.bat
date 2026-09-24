@echo off
REM ==============================================================================
REM  Meta Creator — One-Click Windows Launcher (Portable & Installer Edition)
REM
REM  Starts the local dashboard server, waits until it ACTUALLY answers an HTTP
REM  request, and only then opens the browser. If the server fails to start this
REM  window stays open and shows the captured server log instead of silently
REM  opening a dead "This site can't be reached" page.
REM ==============================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Meta Creator Launcher

set "APP_DIR=%~dp0"
set "PORT=3070"
set "LOG_DIR=%~dp0logs"
set "SERVER_LOG=%LOG_DIR%\server.log"
set "SERVER_ERR=%LOG_DIR%\server.err.log"
set "HEALTH_URL=http://127.0.0.1:%PORT%/"
set "MAX_WAIT=30"

echo ==============================================================================
echo   Meta Creator — Starting Automation Engine
echo ==============================================================================

REM 1. Verify files are properly extracted (prevent running inside zip)
if not exist "%~dp0public\index.html" (
    echo.
    echo ==============================================================================
    echo  [ERROR] Application files are missing or incomplete!
    echo ==============================================================================
    echo.
    echo  It appears you opened Run.bat directly from inside the ZIP file
    echo  or without extracting all files.
    echo.
    echo  HOW TO FIX:
    echo    1. Close this window.
    echo    2. Right-click 'MetaCreator-Windows-Portable.zip'.
    echo    3. Click 'Extract All...' and choose a destination folder.
    echo    4. Open the extracted folder and double-click Run.bat.
    echo ==============================================================================
    echo.
    pause
    exit /b 1
)

REM 2. Configure hermetic paths for Playwright and Python
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0_internal\ms-playwright"
set "PYTHON_BIN=%~dp0_internal\python.exe"
set "PYTHONPATH=%~dp0"
set "PATH=%~dp0bin;%~dp0_internal;%~dp0_internal\Scripts;%PATH%"

REM 3. If a healthy server is already running, just open it.
call :probe
if "%HEALTHY%"=="1" (
    echo [*] Meta Creator server is already running healthy on port %PORT%.
    echo [*] Opening dashboard...
    start "" "http://localhost:%PORT%"
    exit /b 0
)

REM 4. Clear a stale / unresponsive listener on the port
call :free_port

REM 5. Pick the Node runtime (bundled first, then system PATH)
set "NODE_EXE="
if exist "%~dp0bin\node.exe" set "NODE_EXE=%~dp0bin\node.exe"
if not defined NODE_EXE (
    where node >nul 2>&1 && set "NODE_EXE=node"
)
if not defined NODE_EXE (
    echo [!] Error: Node runtime not found in bin\node.exe or system PATH.
    echo [!] Re-extract the full ZIP, or install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM 6. Start the server detached, capturing stdout/stderr into logs\
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if exist "%SERVER_LOG%" del /q "%SERVER_LOG%" >nul 2>&1
if exist "%SERVER_ERR%" del /q "%SERVER_ERR%" >nul 2>&1

echo [*] Launching server: %NODE_EXE%
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%NODE_EXE%' -ArgumentList 'server.js' -WorkingDirectory '%APP_DIR%' -WindowStyle Hidden -RedirectStandardOutput '%SERVER_LOG%' -RedirectStandardError '%SERVER_ERR%'"
if errorlevel 1 (
    echo [!] Failed to launch the server process.
    pause
    exit /b 1
)

REM 7. Wait for a real HTTP response (a listening socket alone is not enough)
echo [*] Waiting for the dashboard to come online...
set /a WAITED=0
:wait_loop
call :probe
if "%HEALTHY%"=="1" goto :server_ready
set /a WAITED+=1
if %WAITED% GEQ %MAX_WAIT% goto :server_failed
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:server_ready
echo [OK] Meta Creator is active at http://localhost:%PORT%
start "" "http://localhost:%PORT%"
echo [i] You may close this window. To stop the server later, run Stop.bat.
ping -n 2 127.0.0.1 >nul
exit /b 0

:server_failed
echo.
echo ==============================================================================
echo  [ERROR] The Meta Creator server did not respond within %MAX_WAIT% seconds.
echo ==============================================================================
echo  Live logs:  Run-Console.bat
echo  Log files:  %SERVER_LOG%
echo              %SERVER_ERR%
echo.
if exist "%SERVER_ERR%" (
    echo ----- server.err.log (last 25 lines) -----
    powershell -NoProfile -Command "Get-Content -Path '%SERVER_ERR%' -Tail 25 -ErrorAction SilentlyContinue"
    echo ------------------------------------------
)
if exist "%SERVER_LOG%" (
    echo ----- server.log (last 25 lines) -----
    powershell -NoProfile -Command "Get-Content -Path '%SERVER_LOG%' -Tail 25 -ErrorAction SilentlyContinue"
    echo --------------------------------------
)
echo.
echo  Common fixes:
echo    1. Run Stop.bat, then try Run.bat again.
echo    2. Add this folder to your antivirus exclusions (Node is often blocked).
echo    3. Re-extract the full ZIP so bin\node.exe and _internal\ are present.
echo ==============================================================================
echo.
pause
exit /b 1

REM --- helpers -----------------------------------------------------------------

:probe
REM Sets HEALTHY=1 when the dashboard answers HTTP 2xx/3xx/4xx on the port.
set "HEALTHY=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 set "HEALTHY=1"
exit /b 0

:free_port
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [*] Port %PORT% is occupied by a stale process. Cleaning up...
    powershell -NoProfile -NonInteractive -Command "$p = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }" >nul 2>&1
    timeout /t 1 >nul
)
exit /b 0
