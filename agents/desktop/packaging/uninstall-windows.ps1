<#
.SYNOPSIS
    Removes the NetQuota agent scheduled task and files.
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\NetQuota",
    [string]$ConfigDir  = "$env:ProgramData\NetQuota",
    [string]$TaskName   = "NetQuotaAgent",
    [switch]$PurgeData
)

$ErrorActionPreference = "Continue"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
if ($PurgeData) {
    Remove-Item -Recurse -Force $ConfigDir -ErrorAction SilentlyContinue
}
Write-Host "NetQuota agent removed."
Write-Host "Remember to revoke this device in the dashboard to invalidate its credential."