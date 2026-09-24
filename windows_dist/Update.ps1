$ErrorActionPreference = 'Stop'
$root = (Split-Path -Parent $MyInvocation.MyCommand.Path).TrimEnd('\')
Set-Location -LiteralPath $root

function Write-Step([string]$message) {
    Write-Host $message
}

function Stop-CreatorProcesses {
    $task = Get-ScheduledTask -TaskName 'MetaSrv' -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName 'MetaSrv' -ErrorAction SilentlyContinue
    }

    $rootPrefix = $root + '\'
    $self = [int]$PID
    $parent = 0
    try {
        $selfProc = Get-CimInstance Win32_Process -Filter "ProcessId=$self" -ErrorAction SilentlyContinue
        if ($selfProc) { $parent = [int]$selfProc.ParentProcessId }
    } catch {}
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        $pidValue = [int]$proc.ProcessId
        if ($pidValue -eq $self -or $pidValue -eq $parent) { continue }
        $exe = [string]$proc.ExecutablePath
        $cmd = [string]$proc.CommandLine
        $inside = ($exe -and $exe.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase))
        $appCommand = ($cmd -and $cmd -match '(?i)(server\.js|worker\.py|Run\.bat|Run-Console\.bat|run_dev\.bat|open_dash\.bat|open_chrome\.bat)')
        if ($inside -or $appCommand) {
            try { Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
    Start-Sleep -Seconds 2
}

function Start-Creator {
    $runBat = Join-Path $root 'Run.bat'
    if (-not (Test-Path -LiteralPath $runBat)) {
        throw "Launcher not found: $runBat"
    }
    Start-Process -FilePath $env:ComSpec -ArgumentList '/d', '/c', "`"$runBat`"" -WorkingDirectory $root | Out-Null
}

function Backup-UserData {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backup = Join-Path $root ("backups\backup_{0}_patch" -f $stamp)
    $hasData = $false
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    foreach ($name in @('data', 'license_data')) {
        $src = Join-Path $root $name
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $backup $name) -Recurse -Force
            $hasData = $true
        }
    }
    $accounts = Join-Path $root 'accounts.txt'
    if (Test-Path -LiteralPath $accounts) {
        Copy-Item -LiteralPath $accounts -Destination (Join-Path $backup 'accounts.txt') -Force
        $hasData = $true
    }
    if ($hasData) { Write-Step "[OK] Backup created: $backup" }
    else { Write-Step '[i] No existing user data found; clean install mode.' }
}

function Find-UpdatePackage {
    foreach ($name in @('update.zip', 'MetaCreator-Windows-Patch.zip', 'MetaCreator-Windows-Portable.zip')) {
        $candidate = Join-Path $root $name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Read-CookieHeaderForAccount($account) {
    $id = [string]$account.id
    if ([string]::IsNullOrWhiteSpace($id)) { return '' }
    $safe = $id -replace '[^A-Za-z0-9_@.\-]', ''
    if ([string]::IsNullOrWhiteSpace($safe)) { return '' }
    $file = Join-Path $root ("cookies\cookies_{0}.txt" -f $safe)
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return '' }
    try {
        $parsed = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($parsed -isnot [System.Array]) { return '' }
        $pairs = foreach ($cookie in $parsed) {
            if ($cookie -and $cookie.name) {
                '{0}={1}' -f $cookie.name, [string]$cookie.value
            }
        }
        return (($pairs | Where-Object { $_ }) -join '; ')
    } catch {
        return ''
    }
}

function Get-IgAccounts($accounts) {
    return @($accounts | Where-Object {
        $status = [string]$_.status
        $status -ne 'MetaCreated' -and (
            [string]$_.instagram_username -or
            [string]$_.platform -match 'Instagram' -or
            $status -in @('Created', 'Verified', 'Submitted')
        )
    })
}

function Export-IgCsv($accounts) {
    $rows = @()
    $rows += 'username,password,cookies,combo'
    foreach ($account in (Get-IgAccounts $accounts)) {
        $username = [string]($account.instagram_username)
        if ([string]::IsNullOrWhiteSpace($username)) { $username = [string]$account.username }
        $password = [string]$account.password
        if ([string]::IsNullOrWhiteSpace($username) -or [string]::IsNullOrWhiteSpace($password)) { continue }
        $cookies = Read-CookieHeaderForAccount $account
        $combo = '{0}|{1}|{2}' -f $username, $password, $cookies
        $escape = {
            param([string]$value)
            $value = [string]$value
            if ($value.IndexOf('"') -ge 0 -or $value.IndexOf(',') -ge 0 -or $value.IndexOf("`n") -ge 0 -or $value.IndexOf("`r") -ge 0) {
                return '"' + $value.Replace('"', '""') + '"'
            }
            return $value
        }
        $rows += ('{0},{1},{2},{3}' -f (&$escape $username), (&$escape $password), (&$escape $cookies), (&$escape $combo))
    }
    return (($rows -join "`r`n") + "`r`n")
}

Write-Host ''
Write-Host '=============================================================================='
Write-Host '  META CREATOR — SAFE IN-PLACE UPDATER'
Write-Host '=============================================================================='
Write-Host ''

Write-Step '[*] Step 1/3: Stopping active Meta Creator processes...'
Stop-CreatorProcesses
Write-Step '[OK] Background processes stopped.'

Write-Step '[*] Step 2/3: Backing up user data and license...'
Backup-UserData

Write-Step '[*] Step 3/3: Locating and applying update package...'
$package = Find-UpdatePackage
if (-not $package) {
    Write-Host '[i] No update archive was found.'
    Start-Creator
    exit 0
}

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($package)
    try {
        foreach ($entry in $zip.Entries) {
            if ([string]::IsNullOrEmpty($entry.Name)) { continue }
            $relative = $entry.FullName.Replace('\', '/')
            if ($relative.StartsWith('MetaCreator/', [StringComparison]::OrdinalIgnoreCase)) {
                $relative = $relative.Substring(12)
            }
            if ([string]::IsNullOrWhiteSpace($relative)) { continue }
            $first = ($relative -split '/')[0].ToLowerInvariant()
            if ($first -in @('data', 'license_data', 'cookies', 'profiles', 'screens', 'logs', 'backups', 'sessions', 'telegram_profiles') -or $relative -eq 'accounts.txt') {
                continue
            }
            $destination = [IO.Path]::GetFullPath((Join-Path $root $relative))
            if (-not $destination.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Unsafe archive path: $relative"
            }
            $parent = [IO.Path]::GetDirectoryName($destination)
            [IO.Directory]::CreateDirectory($parent) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $true)
        }
    } finally {
        $zip.Dispose()
    }

    foreach ($legacy in @('mail_providers.py', 'mem_guard.py', 'core\mail_fish.py')) {
        $path = Join-Path $root $legacy
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
        if (Test-Path -LiteralPath $path) { throw "Could not remove retired provider file: $legacy" }
    }

    foreach ($required in @('ai_config.py', 'core\mailbox.py', 'engine\eng_mix_mail.py', 'worker.py', 'runner.py', 'Update.bat', 'Update.ps1')) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $required) -PathType Leaf)) {
            throw "Updated file is missing: $required"
        }
    }
    $config = Get-Content -LiteralPath (Join-Path $root 'ai_config.py') -Raw -Encoding UTF8
    if ($config -notmatch 'MAIL_PROVIDERS\s*=\s*\("mailtd",\)') {
        throw 'mail.td-only configuration marker was not found.'
    }
    Write-Step '[OK] Code update applied; mail.td-only runtime verified.'
    Start-Creator
    exit 0
} catch {
    Write-Host ('[ERROR] Update failed: ' + $_.Exception.Message)
    Write-Host '[ERROR] Existing user data and backup were left intact.'
    Start-Creator
    exit 1
}
