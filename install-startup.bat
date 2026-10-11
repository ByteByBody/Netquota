@echo off
REM Register NetQuota to run (hidden) at every Windows login.
REM This installs the user-PATH entry, records the role, and creates a hidden
REM Startup shortcut that launches the supervisor with no console window.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bin\net-quota.ps1" install -Startup
pause
