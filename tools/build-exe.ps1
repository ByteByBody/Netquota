# Build the self-contained NetQuota launcher (dist\net-quota.exe).
#
# The launcher bundles the desktop agent so an agent-only machine needs nothing
# else installed (no Python, no git). Run from the repo root:
#
#   powershell -ExecutionPolicy Bypass -File tools\build-exe.ps1
#
param(
    [string]$Python = "server\.venv\Scripts\python.exe"
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    & $Python -m pip install --quiet pyinstaller
    & $Python -m PyInstaller `
        --noconfirm --clean --onefile --console `
        --name net-quota `
        --paths tools --paths agents/desktop `
        --collect-submodules netquota_agent `
        --distpath dist --workpath build\net-quota --specpath build `
        tools\netquota_launcher\__main__.py
    Write-Host "`nBuilt: $repo\dist\net-quota.exe" -ForegroundColor Green
}
finally {
    Pop-Location
}
