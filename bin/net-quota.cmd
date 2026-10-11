@echo off
REM Shim for the net-quota PowerShell tool. Accepts -switch or --switch forms.
set "ARGS=%*"
set "ARGS=%ARGS:--=-%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0net-quota.ps1" %ARGS%
