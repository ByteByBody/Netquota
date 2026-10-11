<#
    NetQuota - update the agent on THIS PC (no re-enrollment).

    Run it in a normal PowerShell window:

        powershell -ExecutionPolicy Bypass -File .\setup-friend.ps1

    What it does:
      1. Finds your NetQuota folder automatically.
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

$ErrorActionPreference = 'Stop'

function Info  { param($m) Write-Host $m -ForegroundColor Cyan }
function OK    { param($m) Write-Host "  OK: $m" -ForegroundColor Green }
function Warn2 { param($m) Write-Host "  WARN: $m" -ForegroundColor Yellow }

# --- 1. Locate the NetQuota folder ----------------------------------------- #
Info "Locating the NetQuota folder..."
$repo = $null
$candidates = @(
    'C:\netquota',
    (Join-Path $env:USERPROFILE 'netquota'),
    (Join-Path $env:USERPROFILE 'projects\netquota'),
    (Join-Path $env:USERPROFILE 'Desktop\netquota'),
    'C:\Users\Public\netquota'
)
foreach ($c in $candidates) {
    if ($c -and (Test-Path (Join-Path $c 'bin\net-quota.ps1'))) { $repo = $c; break }
}
if (-not $repo) {
    $hit = Get-ChildItem -Path 'C:\' -Filter 'net-quota.ps1' -Recurse -Depth 4 -File -ErrorAction SilentlyContinue |
           Where-Object { $_.DirectoryName -match '\\bin$' } | Select-Object -First 1
    if ($hit) { $repo = Split-Path $hit.DirectoryName -Parent }
}
if (-not $repo) {
    throw ("Couldn't find the NetQuota folder automatically. Find the folder that contains 'bin', then run:  " +
           "cd <that folder>; git pull; powershell -ExecutionPolicy Bypass -File .\bin\net-quota.ps1 install -Role agent -Startup")
}
OK "Found: $repo"

# --- 2. Update the code ----------------------------------------------------- #
Info "Updating the code..."
if (Test-Path (Join-Path $repo '.git')) {
    git -C $repo pull origin main
    if ($LASTEXITCODE -ne 0) { Warn2 "git pull failed (offline?); continuing with the existing code." }
} else {
    Warn2 "No .git folder; skipping the update."
}

# --- 3. Refresh the agent package (safe to repeat) -------------------------- #
$py = Join-Path $repo 'agents\desktop\.venv\Scripts\python.exe'
if (Test-Path $py) {
    & $py -m pip install -e (Join-Path $repo 'agents\desktop') -q
} else {
    Warn2 "Agent virtualenv not found at $py; the agent may need a full reinstall."
}

# --- 4. Install the net-quota command + hidden auto-start (agent role) ------ #
Info "Installing the net-quota command (hidden auto-start)..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'bin\net-quota.ps1') install -Role agent -Startup

# --- 5. Start it now, hidden ------------------------------------------------ #
$vbs = Join-Path $repo 'bin\net-quota-hidden.vbs'
if (Test-Path $vbs) {
    Info "Starting the agent now (hidden)..."
    Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + $vbs + '"')
} else {
    Warn2 "Hidden launcher not found; run 'net-quota run' manually."
}

# --- 6. Status -------------------------------------------------------------- #
Start-Sleep -Seconds 5
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'bin\net-quota.ps1') status

Write-Host ""
Write-Host "Done. NetQuota runs hidden and starts automatically at login." -ForegroundColor Green
Write-Host "Commands:  net-quota status | net-quota stop | net-quota run" -ForegroundColor Cyan
