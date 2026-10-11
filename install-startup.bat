@echo off
REM Install NetQuota to Windows Startup (runs on every login)

set SCRIPT_PATH=C:\Users\me_meansnothing\projects\netquota\start-netquota.bat
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_NAME=NetQuota Auto-Start.lnk

powershell.exe -NoProfile -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; " ^
    "$Shortcut = $WshShell.CreateShortcut('%STARTUP_DIR%\%SHORTCUT_NAME%'); " ^
    "$Shortcut.TargetPath = '%SCRIPT_PATH%'; " ^
    "$Shortcut.WorkingDirectory = 'C:\Users\me_meansnothing\projects\netquota'; " ^
    "$Shortcut.Description = 'Starts NetQuota backend, dashboard, and agent on login'; " ^
    "$Shortcut.Save()"

echo Shortcut created in Startup folder.
echo NetQuota will start automatically on next login.
pause