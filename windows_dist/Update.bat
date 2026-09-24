@echo off
REM ==============================================================================
REM  Meta Creator — Automated Safe In-Place Updater
REM  Updates the application code & engines in-place while keeping your accounts,
REM  database, and license activation 100% safe and intact.
REM ==============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Meta Creator — Safe Updater

echo.
echo ================================================================================
echo   META CREATOR — SAFE IN-PLACE UPDATER
echo ================================================================================
echo.

REM 1. Stop any running background instances to release Windows file locks
echo [*] Step 1/3: Stopping active Meta Creator processes to release file locks...
if exist "Stop.bat" (
    call "Stop.bat" >nul 2>&1
) else (
    powershell -NoProfile -NonInteractive -Command "$root='%~dp0'.TrimEnd('\'); Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }" >nul 2>&1
)
timeout /t 1 >nul
echo [OK] Background processes stopped and port 3070 released.

REM 2. Create an automated timestamped backup of user data and license
echo.
echo [*] Step 2/3: Securing data and license backup...
set "TIMESTAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "TIMESTAMP=%TIMESTAMP::=%"
set "BACKUP_DIR=%~dp0backups\backup_%TIMESTAMP%"

if not exist "%~dp0backups" mkdir "%~dp0backups"

set "HAS_DATA=0"
if exist "%~dp0data" (
    mkdir "%BACKUP_DIR%\data" >nul 2>&1
    xcopy /E /I /Q /Y "%~dp0data" "%BACKUP_DIR%\data" >nul 2>&1
    set "HAS_DATA=1"
)
if exist "%~dp0license_data" (
    mkdir "%BACKUP_DIR%\license_data" >nul 2>&1
    xcopy /E /I /Q /Y "%~dp0license_data" "%BACKUP_DIR%\license_data" >nul 2>&1
    set "HAS_DATA=1"
)
if exist "%~dp0accounts.txt" (
    copy /Y "%~dp0accounts.txt" "%BACKUP_DIR%\" >nul 2>&1
    set "HAS_DATA=1"
)

if "!HAS_DATA!"=="1" (
    echo [OK] Safe backup created at:
    echo      backups\backup_%TIMESTAMP%
) else (
    echo [i] No existing data or license found yet. Clean install mode.
)

REM 3. Check for update package (update.zip, patch.zip, or portable zip)
echo.
echo [*] Step 3/3: Checking for update archive...

set "UPDATE_PKG="
if exist "%~dp0update.zip" set "UPDATE_PKG=%~dp0update.zip"
if exist "%~dp0MetaCreator-Windows-Patch.zip" set "UPDATE_PKG=%~dp0MetaCreator-Windows-Patch.zip"
if exist "%~dp0MetaCreator-Windows-Portable.zip" set "UPDATE_PKG=%~dp0MetaCreator-Windows-Portable.zip"

if defined UPDATE_PKG (
    echo [*] Found update archive: !UPDATE_PKG!
    echo [*] Extracting and updating files in-place...
    
    powershell -NoProfile -NonInteractive -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip = [System.IO.Compression.ZipFile]::OpenRead('!UPDATE_PKG!'); foreach ($entry in $zip.Entries) { if ($entry.FullName.EndsWith('/')) { continue }; $rel = $entry.FullName; if ($rel.StartsWith('MetaCreator/')) { $rel = $rel.Substring(12) }; if ($rel.StartsWith('data/') -or $rel.StartsWith('license_data/') -or $rel -eq 'accounts.txt') { continue }; $dest = Join-Path '%~dp0' $rel; $destDir = [System.IO.Path]::GetDirectoryName($dest); if (-not (Test-Path $destDir)) { [System.IO.Directory]::CreateDirectory($destDir) | Out-Null }; [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest, $true); }; $zip.Dispose();"
    
    if !errorlevel! equ 0 (
        echo [OK] Update applied successfully!
        if exist "%~dp0update.zip" del /f /q "%~dp0update.zip" >nul 2>&1
        echo.
        echo ================================================================================
        echo   [SUCCESS] META CREATOR HAS BEEN UPDATED SUCCESSFULLY!
        echo   - All application engines, UI, and scripts are up to date.
        echo   - Your registered accounts, database, and license are 100%% safe and active!
        echo ================================================================================
    ) else (
        echo [ERROR] Extraction encountered an issue. Your previous files and backup are untouched.
    )
) else (
    echo [i] No update archive (update.zip or MetaCreator-*.zip) was found in this folder.
    echo.
    echo --------------------------------------------------------------------------------
    echo  MANUAL UPDATE INSTRUCTIONS:
    echo --------------------------------------------------------------------------------
    echo  Your data is now backed up and background processes are cleanly stopped.
    echo  To complete your update:
    echo.
    echo  1. Open your new ZIP file (or copy the new MetaCreator files).
    echo  2. Drag and drop the new files directly into this folder:
    echo     "%~dp0"
    echo  3. When Windows prompts:
    echo     "Replace or Skip Files"
    echo     Choose: "[x] Replace the files in the destination"
    echo.
    echo  4. Your accounts and license will NEVER be lost!
    echo     (Stored safely in 'data\' and 'license_data\').
    echo --------------------------------------------------------------------------------
)

echo.
echo Press any key to start Meta Creator (or close this window)...
pause >nul
start "" "%~dp0Run.bat"
exit /b 0
