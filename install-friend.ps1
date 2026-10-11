<# 
.SYNOPSIS
    NetQuota Windows Agent - One-Command Installer
.DESCRIPTION
    Clones repo, sets up venv, enrolls device, configures home-network counting,
    installs auto-start, and starts the agent.
.NOTES
    Run in PowerShell as Administrator.
    Requires: Git, internet access.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerUrl,

    [Parameter(Mandatory=$true)]
    [string]$EnrollmentCode,

    [Parameter(Mandatory=$true)]
    [string]$DeviceName,

    [string]$RepoUrl = "https://github.com/ByteByBody/Netquota.git",
    [string]$InstallPath = "C:\netquota",
    [switch]$NoAutoStart
)

# ---- Helpers ----
function Write-Step { param([string]$msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  WARN: $msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$msg) Write-Host "`n  ERR: $msg" -ForegroundColor Red; exit 1 }

# ---- Pre-flight ----
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Must run as Administrator. Right-click PowerShell -> Run as Administrator."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "Git not found. Install from https://git-scm.com"
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Err "Python not found. Install from https://python.org (check 'Add to PATH')."
}

Write-Step "NetQuota Agent Installer"
Write-Host "Server:      $ServerUrl"
Write-Host "Code:        $EnrollmentCode"
Write-Host "Device Name: $DeviceName"
Write-Host "Install to:  $InstallPath"

# ---- 0. Server reachability ----
# The #1 cause of a confusing "enrollment failed" is the server being
# unreachable (host off, bound to loopback only, or firewall). Check first.
Write-Step "Checking server reachability"
try {
    $health = Invoke-WebRequest -Uri "$($ServerUrl.TrimEnd('/'))/health" -UseBasicParsing -TimeoutSec 8
    Write-OK "Server reachable (HTTP $($health.StatusCode))"
} catch {
    Write-Err "Cannot reach server at $ServerUrl. Make sure the host PC is on, NetQuota backend is running, and inbound TCP 8000 is allowed by its firewall. Details: $($_.Exception.Message)"
}

# ---- 1. Clone ----
Write-Step "Cloning repository"
if (Test-Path $InstallPath) {
    Write-Host "  Path exists, pulling latest..." -ForegroundColor Yellow
    Set-Location $InstallPath
    git pull origin main 2>&1 | Out-Null
} else {
    git clone $RepoUrl $InstallPath 2>&1 | Out-Null
}
Write-OK "Repository ready at $InstallPath"

# ---- 2. Python venv ----
Write-Step "Creating Python virtual environment"
$VenvPath = Join-Path $InstallPath "agents\desktop\.venv"
if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath 2>&1 | Out-Null
}
$AgentExe = Join-Path $VenvPath "Scripts\netquota-agent.exe"
if (-not (Test-Path $AgentExe)) {
    Write-Err "Agent entry point missing at $AgentExe"
}
Write-OK "Venv at $VenvPath"

# ---- 3. Install agent ----
Write-Step "Installing agent package"
& "$VenvPath\Scripts\python.exe" -m pip install -e "$InstallPath\agents\desktop" -q 2>&1 | Out-Null
if (-not (Test-Path $AgentExe)) {
    Write-Err "Agent install failed (no netquota-agent.exe)."
}
Write-OK "Agent installed"

# ---- 4. Enroll ----
Write-Step "Enrolling device"
$EnrollOutput = (& $AgentExe enroll --server $ServerUrl --code $EnrollmentCode --name $DeviceName 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Err "Enrollment failed.`n  $EnrollOutput`n  (Common causes: invalid/expired/used code, or server unreachable.)"
}
Write-Host "  $EnrollOutput"
Write-OK "Enrolled"

# ---- 5. Detect & set gateway MAC ----
Write-Step "Detecting gateway MAC"
$Mac = $null
$MacOutput = (& $AgentExe detect-gateway 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -eq 0) {
    $Mac = ($MacOutput -split ': ')[-1].Trim()
}
if ($Mac -and $Mac -match '^([0-9a-f]{2}:){5}[0-9a-f]{2}$') {
    Write-Step "Enabling home-network counting"
    $SetOutput = (& $AgentExe set-gateway $Mac 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Could not enable home-network counting: $SetOutput"
    } else {
        Write-OK "Home-network counting enabled (gateway $Mac)"
    }
} else {
    Write-Warn "Could not determine the gateway MAC; this device will count ALL traffic."
    Write-Warn "Re-run later: netquota-agent detect-gateway ; netquota-agent set-gateway <MAC>"
}

# ---- 6. Set 5s interval ----
Write-Step "Setting report interval to 5 seconds"
$ConfigPath = Join-Path $env:ProgramData "NetQuota\agent.json"
if (Test-Path $ConfigPath) {
    try {
        $Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        $Config.interval_seconds = 5
        $Config | ConvertTo-Json -Depth 5 | Set-Content $ConfigPath -Encoding UTF8
        Write-OK "Interval set to 5s"
    } catch {
        Write-Warn "Could not update $ConfigPath : $($_.Exception.Message)"
    }
} else {
    Write-Warn "Config not found at $ConfigPath (will be created on first run)"
}

# ---- 7. Auto-start (optional) ----
if (-not $NoAutoStart) {
    Write-Step "Installing auto-start on login"
    $StartupScript = @"
@echo off
cd /d $InstallPath\agents\desktop
call .venv\Scripts\activate.bat
netquota-agent run
"@
    $BatPath = Join-Path $InstallPath "agents\desktop\run-agent.bat"
    $StartupScript | Set-Content $BatPath -Encoding ASCII

    $StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
    $ShortcutPath = Join-Path $StartupDir "NetQuota Agent.lnk"
    $Wsh = New-Object -ComObject WScript.Shell
    $Sc = $Wsh.CreateShortcut($ShortcutPath)
    $Sc.TargetPath = "cmd.exe"
    $Sc.Arguments = "/c `"$BatPath`""
    $Sc.WorkingDirectory = Join-Path $InstallPath "agents\desktop"
    $Sc.Description = "NetQuota Agent - starts on login"
    $Sc.Save()
    Write-OK "Auto-start installed (runs on next login)"
}

# ---- 8. Test sample ----
Write-Step "Testing sample collection"
$SampleOutput = (& $AgentExe sample 2>&1 | Out-String).Trim()
Write-Host $SampleOutput
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Sample collection returned a non-zero exit; agent may still work."
} else {
    Write-OK "Sample OK"
}

# ---- 9. Start agent now ----
Write-Step "Starting agent (runs in a separate window)"
Start-Process "cmd.exe" -ArgumentList "/k", "cd /d `"$InstallPath\agents\desktop`" && call .venv\Scripts\activate.bat && netquota-agent run" -WorkingDirectory (Join-Path $InstallPath "agents\desktop")

Write-Host "`n=== INSTALL COMPLETE ===" -ForegroundColor Green
Write-Host "Device enrolled and reporting every 5s."
Write-Host "Dashboard (on the host PC): $ServerUrl  ->  open port 5173 for the UI"
Write-Host "Agent window opened - leave it running."
Write-Host "Auto-start: runs on next login." -ForegroundColor Cyan
