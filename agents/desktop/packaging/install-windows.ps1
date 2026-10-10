<#
.SYNOPSIS
    Installs the NetQuota desktop agent as a Windows scheduled task that starts
    at system boot and runs as LocalSystem (or a dedicated account).

.NOTES
    Enrollment must be performed first, or afterward as the same account, so the
    credential is readable by the task's account. For a per-user install, run the
    task as that user instead of LocalSystem.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install-windows.ps1 -PythonPath "C:\Python312\python.exe"
#>
param(
    [string]$PythonPath = "python",
    [string]$InstallDir = "$env:ProgramFiles\NetQuota",
    [string]$ConfigDir  = "$env:ProgramData\NetQuota",
    [string]$TaskName   = "NetQuotaAgent"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing NetQuota agent to $InstallDir ..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

$source = Resolve-Path (Join-Path $PSScriptRoot "..")
Copy-Item -Recurse -Force $source (Join-Path $InstallDir "agent")

Write-Host "Installing Python dependencies ..."
& $PythonPath -m pip install --upgrade (Join-Path $InstallDir "agent[secure]")

$env:NETQUOTA_AGENT_CONFIG_DIR = $ConfigDir
$script = Join-Path $InstallDir "agent\agent.py"

Write-Host "Registering scheduled task '$TaskName' (run at startup) ..."
$action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$script`" run" `
    -WorkingDirectory (Join-Path $InstallDir "agent")
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Done."
Write-Host "Enroll with:"
Write-Host "  `$env:NETQUOTA_AGENT_CONFIG_DIR='$ConfigDir'"
Write-Host "  $PythonPath agent.py enroll --server https://netquota.local --code <CODE> --name `"<NAME>`""