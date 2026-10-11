@echo off
REM NetQuota manual launcher.
REM Starts the supervisor in THIS window (components run hidden by default).
REM Tip: run "net-quota run --show" to see component windows while debugging.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bin\net-quota.ps1" run %*
