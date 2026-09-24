@echo off
REM ==============================================================================
REM  Meta Creator — Safe Process Termination
REM  Terminates only Meta Creator background processes and frees port 3070.
REM ==============================================================================
setlocal
cd /d "%~dp0"
title Stopping Meta Creator...

echo [*] Stopping Meta Creator server and workers...

REM 1. Safely stop processes whose executable path is within this folder
powershell -NoProfile -NonInteractive -Command "$root='%~dp0'.TrimEnd('\'); Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force; Write-Output ('Stopped PID ' + $_.ProcessId + ' (' + $_.Name + ')') } catch {} }"

REM 2. Free port 3070 if still bound
powershell -NoProfile -NonInteractive -Command "$p = Get-NetTCPConnection -LocalPort 3070 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Output ('Freed port 3070 from PID ' + $p) }"

echo.
echo [OK] Meta Creator server and workers have been stopped cleanly.
timeout /t 2 >nul
exit /b 0
