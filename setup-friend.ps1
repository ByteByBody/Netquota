<#
    NetQuota - update the agent on THIS PC (no re-enrollment).

    Run it in a normal PowerShell window:

        powershell -ExecutionPolicy Bypass -File .\setup-friend.ps1

    If it can't find your NetQuota folder, point it straight at the folder:

        powershell -ExecutionPolicy Bypass -File .\setup-friend.ps1 -RepoPath "C:\netquota"

    What it does:
      1. Finds your NetQuota folder (the one with install-friend.ps1 / agents).
      2. Pulls the latest code.
      3. Installs the `net-quota` command with a HIDDEN auto-start (agent role).
      4. Starts the agent now (hidden) and prints the status.

    Your PC stays enrolled as the same device - this does NOT create a new one.
    Administrator is not required (if you hit a permissions error, re-run as admin).

    Afterwards:
      net-quota status   - is it running?
      net-quota stop     - stop it
      net-quota run      - start it again (open a NEW window first)
#>

param(
    [string]$RepoPath = ''
)

$ErrorActionPreference = 'Stop'

function Info  { param($m) Write-Host $m -ForegroundColor Cyan }
function OK    { param($m) Write-Host "  OK: $m" -ForegroundColor Green }
function Warn2 { param($m) Write-Host "  WARN: $m" -ForegroundColor Yellow }

# A folder is a NetQuota checkout if it has any of these (pre- or post-pull).
function Test-NetQuotaRepo {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) { return $false }
    if (Test-Path -LiteralPath (Join-Path $Path 'bin\net-quota.ps1')) { return $true }
    if (Test-Path -LiteralPath (Join-Path $Path 'install-friend.ps1')) { return $true }
    if ((Test-Path -LiteralPath (Join-Path $Path '.git')) -and
        (Test-Path -LiteralPath (Join-Path $Path 'agents\desktop'))) { return $true }
    return $false
}

# --- 1. Locate the NetQuota folder ----------------------------------------- #
Info "Locating the NetQuota folder..."
$repo = $null

if ($RepoPath) {
    if (Test-NetQuotaRepo $RepoPath) { $repo = $RepoPath }
    else { throw "The -RepoPath you gave doesn't look like a NetQuota folder: $RepoPath" }
}

$candidates = @(
    'C:\netquota', 'D:\netquota',
    (Join-Path $env:USERPROFILE 'netquota'),
    (Join-Path $env:USERPROFILE 'projects\netquota'),
    (Join-Path $env:USERPROFILE 'source\repos\netquota'),
    (Join-Path $env:USERPROFILE 'source\repos\Netquota'),
    (Join-Path $env:USERPROFILE 'Desktop\netquota'),
    (Join-Path $env:USERPROFILE 'Documents\netquota'),
    'C:\Users\Public\netquota'
)
if (-not $repo) {
    foreach ($c in $candidates) {
        if (Test-NetQuotaRepo $c) { $repo = $c; break }
    }
}

# Fallback: look for a folder named "netquota" on each fixed drive.
if (-not $repo) {
    Info "  Not in the usual places; searching drives (this can take a moment)..."
    $drives = Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue |
              Where-Object { $_.Root -match '^[A-Za-z]:\\$' } | ForEach-Object { $_.Root }
    foreach ($root in $drives) {
        $dirs = Get-ChildItem -LiteralPath $root -Directory -Recurse -Depth 4 -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -ieq 'netquota' }
        foreach ($d in $dirs) {
            if (Test-NetQuotaRepo $d.FullName) { $repo = $d.FullName; break }
        }
        if ($repo) { break }
    }
}

# Last resort: ask.
if (-not $repo) {
    Write-Host ""
    Write-Host "Couldn't find the NetQuota folder automatically." -ForegroundColor Yellow
    Write-Host "It's the folder that contains 'install-friend.ps1' and an 'agents' folder."
    Write-Host "Run this to locate it, then pass it with -RepoPath:" -ForegroundColor Yellow
    Write-Host '  Get-ChildItem C:\ -Directory -Recurse -Depth 4 -ErrorAction SilentlyContinue | Where-Object { $_.Name -ieq ''netquota'' } | Select-Object -ExpandProperty FullName' -ForegroundColor DarkGray
    $entered = Read-Host "Or paste the full path here (Enter to cancel)"
    if ([string]::IsNullOrWhiteSpace($entered)) { throw "Cancelled: NetQuota folder not found." }
    $entered = $entered.Trim().Trim('"')
    if (Test-NetQuotaRepo $entered) { $repo = $entered }
    else { throw "That folder doesn't look like a NetQuota folder: $entered" }
}
OK "Found: $repo"

# --- 2. Update the code ----------------------------------------------------- #
Info "Updating the code..."
if (Test-Path -LiteralPath (Join-Path $repo '.git')) {
    git -C $repo pull origin main
    if ($LASTEXITCODE -ne 0) { Warn2 "git pull failed (offline?); continuing with the existing code." }
} else {
    Warn2 "No .git folder; skipping the update."
}

$nq = Join-Path $repo 'bin\net-quota.ps1'
if (-not (Test-Path -LiteralPath $nq)) {
    throw "net-quota.ps1 is still missing after the update. The folder may be an old copy, not a git checkout. Ask Abdallah for help."
}

# --- 3. Refresh the agent package (safe to repeat) -------------------------- #
$py = Join-Path $repo 'agents\desktop\.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $py) {
    & $py -m pip install -e (Join-Path $repo 'agents\desktop') -q
} else {
    Warn2 "Agent virtualenv not found at $py; the agent may need a full reinstall."
}

# --- 4. Install the net-quota command + hidden auto-start (agent role) ------ #
Info "Installing the net-quota command (hidden auto-start)..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $nq install -Role agent -Startup

# --- 5. Start it now, hidden ------------------------------------------------ #
$vbs = Join-Path $repo 'bin\net-quota-hidden.vbs'
if (Test-Path -LiteralPath $vbs) {
    Info "Starting the agent now (hidden)..."
    Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + $vbs + '"')
} else {
    Warn2 "Hidden launcher not found; run 'net-quota run' manually."
}

# --- 6. Status -------------------------------------------------------------- #
Start-Sleep -Seconds 5
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $nq status

Write-Host ""
Write-Host "Done. NetQuota runs hidden and starts automatically at login." -ForegroundColor Green
Write-Host "Commands:  net-quota status | net-quota stop | net-quota run" -ForegroundColor Cyan
