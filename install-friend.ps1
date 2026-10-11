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
function Write-Err  { param([string]$msg) Write-Host "  ERR: $msg" -ForegroundColor Red; exit 1 }

# ---- Pre-flight ----
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Must run as Administrator. Right-click PowerShell -> Run as Administrator."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "Git not found. Install from https://git-scm.com"
}

Write-Step "NetQuota Agent Installer"
Write-Host "Server:      $ServerUrl"
Write-Host "Code:        $EnrollmentCode"
Write-Host "Device Name: $DeviceName"
Write-Host "Install to:  $InstallPath"

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
Write-OK "Venv at $VenvPath"

# ---- 3. Install agent ----
Write-Step "Installing agent package"
& "$VenvPath\Scripts\pip.exe" install -e "$InstallPath\agents\desktop" -q 2>&1 | Out-Null
Write-OK "Agent installed"

# ---- 4. Enroll ----
Write-Step "Enrolling device"
$EnrollCmd = "& `"$VenvPath\Scripts\netquota-agent.exe`" enroll --server $ServerUrl --code $EnrollmentCode --name `"$DeviceName`""
$Result = Invoke-Expression $EnrollCmd 2>&1
if ($LASTEXITCODE -ne 0) { Write-Err "Enrollment failed: $Result" }
Write-Host $Result
Write-OK "Enrolled"

# ---- 5. Detect & set gateway MAC ----
Write-Step "Detecting gateway MAC"
$DetectCmd = "& `"$VenvPath\Scripts\netquota-agent.exe`" detect-gateway"
$MacResult = Invoke-Expression $DetectCmd 2>&1
if ($LASTEXITCODE -ne 0) { Write-Err "Gateway detection failed: $MacResult" }
Write-Host $Result
$Mac = ($MacResult -split ': ')[-1].Trim()
if (-not $Mac -or $Mac -notmatch '^([0-9a-f]{2}:){5}[0-9a-f]{2}$') {
    Write-Err "Could not parse MAC from: $MacResult"
}
Write-OK "Gateway MAC: $Mac"

Write-Step "Enabling home-network counting"
$SetCmd = "& `"$VenvPath\Scripts\netquota-agent.exe`" set-gateway $Mac"
$SetResult = Invoke-Expression $SetCmd 2>&1
if ($LASTEXITCODE -ne 0) { Write-Err "Set-gateway failed: $SetResult" }
Write-Host $SetResult
Write-OK "Home-network counting enabled"

# ---- 6. Set 5s interval ----
Write-Step "Setting report interval to 5 seconds"
$ConfigPath = "C:\ProgramData\NetQuota\agent.json"
if (Test-Path $ConfigPath) {
    $Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    $Config.interval_seconds = 5
    $Config | ConvertTo-Json -Depth 5 | Set-Content $ConfigPath
    Write-OK "Interval set to 5s"
} else {
    Write-Host "  Config not found yet (will be created on first run)" -ForegroundColor Yellow
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

    $ShortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\NetQuota Agent.lnk"
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
$SampleCmd = "& `"$VenvPath\Scripts\netquota-agent.exe`" sample"
$SampleResult = Invoke-Expression $SampleCmd 2>&1
Write-Host $SampleResult
Write-OK "Sample OK"

# ---- 9. Start agent now ----
Write-Step "Starting agent (runs in background)"
$RunCmd = "& `"$VenvPath\Scripts\netquota-agent.exe`" run"
Start-Process "cmd.exe" -ArgumentList "/k", "cd /d `"$InstallPath\agents\desktop`" && call .venv\Scripts\activate.bat && netquota-agent run" -WindowStyle Normal

Write-Host "`n=== INSTALL COMPLETE ===" -ForegroundColor Green
Write-Host "Device enrolled and reporting every 5s."
Write-Host "Check dashboard at $ServerUrl (port 5173 for UI)"
Write-Host "Agent window opened - leave it running."
Write-Host "Auto-start: runs on next login." -ForegroundColor Cyan