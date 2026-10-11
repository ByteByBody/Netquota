' NetQuota - launch the supervisor hidden (used by the login auto-start).
' Runs: powershell -WindowStyle Hidden -File net-quota.ps1 run
Option Explicit
Dim fso, sh, scriptDir, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptDir & "\net-quota.ps1"" run"
' 0 = hidden window, False = do not wait
sh.Run cmd, 0, False
