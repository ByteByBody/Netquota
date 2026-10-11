<#
.SYNOPSIS
    net-quota - run / stop / status the NetQuota stack with one command.

.DESCRIPTION
    Starts the NetQuota components for this machine and keeps them alive. If a
    component exits or is closed, it is restarted automatically. Components run
    hidden and write logs under %ProgramData%\NetQuota\logs.

    Roles:
      * host  - backend (:8000) + dashboard (:5173) + agent
      * agent - the reporting agent only

    The role is read from %ProgramData%\NetQuota\role.txt, or inferred from the
    install (a server virtualenv is present => host).

.EXAMPLE
    net-quota run
    net-quota run --show
    net-quota status
    net-quota stop
    net-quota install -Startup
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('run', 'stop', 'status', 'install', 'help')]
    [string]$Command = 'run',

    # run: show the component windows instead of hiding them (debugging).
    [switch]$Show,

    # run: do a single start-if-missing pass, then exit.
    [switch]$Once,

    # install: force the machine role instead of inferring it.
    [ValidateSet('', 'host', 'agent')]
    [string]$Role = '',

    # install: also register the hidden launcher to run at login.
    [switch]$Startup
)

$ErrorActionPreference = 'Stop'

$BinDir       = $PSScriptRoot
$RepoRoot     = Split-Path -Parent $BinDir
$ServerDir    = Join-Path $RepoRoot 'server'
$DashboardDir = Join-Path $RepoRoot 'apps\dashboard'
$AgentDir     = Join-Path $RepoRoot 'agents\desktop'

$DataDir  = Join-Path $env:ProgramData 'NetQuota'
$LogDir   = Join-Path $DataDir 'logs'
$RoleFile = Join-Path $DataDir 'role.txt'
$StopFlag = Join-Path $DataDir 'supervisor.stop'

$script:LastStart = @{}
$CooldownSeconds = 15

# --------------------------------------------------------------------------- #
function Initialize-Dirs {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    New-Item -ItemType Directory -Force -Path $LogDir  | Out-Null
}

function Get-Role {
    if (Test-Path $RoleFile) {
        $r = (Get-Content $RoleFile -Raw).Trim().ToLower()
        if ($r -eq 'host' -or $r -eq 'agent') { return $r }
    }
    if (Test-Path (Join-Path $ServerDir '.venv\Scripts\python.exe')) { return 'host' }
    return 'agent'
}

function Get-AgentExe {
    foreach ($c in @(
        (Join-Path $AgentDir  '.venv\Scripts\netquota-agent.exe'),
        (Join-Path $ServerDir '.venv\Scripts\netquota-agent.exe')
    )) { if (Test-Path $c) { return $c } }
    return $null
}

function Test-Port {
    param([int]$Port)
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-AgentProcesses {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'netquota[-_]agent'
    })
}

function Start-Component {
    param(
        [string]$Name,
        [string]$File,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )
    $out = Join-Path $LogDir "$Name.log"
    $err = Join-Path $LogDir "$Name.err.log"
    $sp = @{
        FilePath               = $File
        ArgumentList           = $Arguments
        WorkingDirectory       = $WorkingDirectory
        RedirectStandardOutput = $out
        RedirectStandardError  = $err
        PassThru               = $true
    }
    if (-not $Show) { $sp['WindowStyle'] = 'Hidden' }
    Start-Process @sp | Out-Null
}

function Start-Backend {
    $py = Join-Path $ServerDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) { Write-Warning "backend python not found: $py"; return }
    $env:NETQUOTA_DATABASE_URL = 'sqlite+aiosqlite:///./netquota.db'
    if (-not $env:NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD) {
        $env:NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD = 'changeme'
    }
    Start-Component -Name 'backend' -File $py `
        -Arguments @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000') `
        -WorkingDirectory $ServerDir
}

function Start-Dashboard {
    if (-not (Test-Path (Join-Path $DashboardDir 'package.json'))) {
        Write-Warning 'dashboard not found'; return
    }
    Start-Component -Name 'dashboard' -File 'cmd.exe' `
        -Arguments @('/c', 'npm run dev') -WorkingDirectory $DashboardDir
}

function Start-Agent {
    $exe = Get-AgentExe
    if (-not $exe) { Write-Warning 'netquota-agent.exe not found'; return }
    Start-Component -Name 'agent' -File $exe -Arguments @('run') -WorkingDirectory $AgentDir
}

function Maybe-Start {
    param([string]$Name, [scriptblock]$Starter)
    $now = Get-Date
    if ($script:LastStart.ContainsKey($Name)) {
        if (($now - $script:LastStart[$Name]).TotalSeconds -lt $CooldownSeconds) { return }
    }
    & $Starter
    $script:LastStart[$Name] = $now
    Write-Host "  [start] $Name" -ForegroundColor Yellow
}

function Invoke-Ensure {
    param([string]$Role)
    Initialize-Dirs
    if ($Role -eq 'host') {
        if (-not (Test-Port 8000)) { Maybe-Start 'backend'   { Start-Backend } }
        if (-not (Test-Port 5173)) { Maybe-Start 'dashboard' { Start-Dashboard } }
    }
    if ((Get-AgentProcesses).Count -eq 0) { Maybe-Start 'agent' { Start-Agent } }
}

# --------------------------------------------------------------------------- #
function Show-Status {
    $role    = Get-Role
    $backend = (Test-Port 8000)
    $dash    = (Test-Port 5173)
    $agent   = ((Get-AgentProcesses).Count -gt 0)

    Write-Host "NetQuota status  (role=$role)" -ForegroundColor Cyan
    foreach ($row in @(
        @{ n = 'backend';   up = $backend; detail = ':8000' },
        @{ n = 'dashboard'; up = $dash;    detail = ':5173' },
        @{ n = 'agent';     up = $agent;   detail = '' }
    )) {
        $state = if ($row.up) { 'UP' } else { 'down' }
        $color = if ($row.up) { 'Green' } else { 'Red' }
        Write-Host ("  {0,-10} {1,-5} {2}" -f $row.n, $state, $row.detail) -ForegroundColor $color
    }
}

# Kill whatever a selector returns, repeating until nothing matches. Repeating
# defeats restart-on-exit wrappers (uvicorn --reload, npm's shell). The selector
# must return objects that carry a ProcessId property.
function Stop-Repeatedly {
    param([scriptblock]$Selector, [int]$Rounds = 6)
    for ($i = 0; $i -lt $Rounds; $i++) {
        $procs = @(& $Selector)
        if ($procs.Count -eq 0) { return }
        $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 400
    }
}

# The process currently listening on a TCP port (as ProcessId-bearing objects).
function Get-PortOwners {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { [pscustomobject]@{ ProcessId = $_ } }
}

function Stop-NetQuota {
    Initialize-Dirs
    # Signal any running supervisor to stop restoring things.
    New-Item -ItemType File -Force -Path $StopFlag | Out-Null
    Start-Sleep -Seconds 4

    Stop-Repeatedly { Get-AgentProcesses }

    Stop-Repeatedly {
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'app\.main:app'
        }
    }

    # Port owners catch workers whose command line no longer names uvicorn
    # (e.g. the multiprocessing child that a --reload server actually serves on).
    Stop-Repeatedly { Get-PortOwners 8000 }
    Stop-Repeatedly { Get-PortOwners 5173 }

    Stop-Repeatedly {
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine -match 'npm(\.cmd)?\s+run\s+dev'
        }
    }

    Remove-Item -Force $StopFlag -ErrorAction SilentlyContinue
}

function Invoke-Run {
    Initialize-Dirs
    Remove-Item -Force $StopFlag -ErrorAction SilentlyContinue
    $role = Get-Role

    # Only the long-running supervisor takes the single-instance lock; -Once is
    # a one-shot helper that must be allowed to run alongside it.
    $mutex = $null
    if (-not $Once) {
        $createdNew = $false
        $mutex = New-Object System.Threading.Mutex($true, 'Local\NetQuotaSupervisor', [ref]$createdNew)
        if (-not $createdNew) {
            Write-Host 'A net-quota supervisor is already running (see: net-quota status).' -ForegroundColor Yellow
            return
        }
    }

    Write-Host "net-quota supervisor (role=$role). Logs: $LogDir" -ForegroundColor Cyan
    Invoke-Ensure -Role $role
    if ($Once) { return }
    Write-Host "Watching components. Stop with Ctrl+C or 'net-quota stop'." -ForegroundColor DarkGray
    while ($true) {
        Start-Sleep -Seconds 3
        if (Test-Path $StopFlag) {
            Write-Host 'Stop requested by another process.' -ForegroundColor Yellow
            break
        }
        Invoke-Ensure -Role $role
    }
    if ($mutex) { $mutex.ReleaseMutex(); $mutex.Dispose() }
}

function Invoke-Install {
    Initialize-Dirs
    $r = $Role
    if (-not $r) { $r = Get-Role }
    Set-Content -Path $RoleFile -Value $r -Encoding ASCII

    # --- Add this folder to the *user* PATH, preserving the registry value kind.
    $bin = $BinDir
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    if ($key) {
        $raw   = $key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $kind  = $key.GetValueKind('Path')
        $parts = @($raw -split ';' | Where-Object { $_ -ne '' })
        if ($parts -notcontains $bin) {
            $key.SetValue('Path', (($parts + $bin) -join ';'), $kind)
            Write-Host "Added to user PATH: $bin" -ForegroundColor Green
            try {
                Add-Type -Namespace Win32 -Name Env -ErrorAction SilentlyContinue -MemberDefinition @'
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
                [UIntPtr]$res = [UIntPtr]::Zero
                [void][Win32.Env]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$res)
            } catch { }
        } else {
            Write-Host "Already on user PATH: $bin"
        }
        $key.Close()
    } else {
        Write-Warning 'Could not open HKCU\Environment to update PATH.'
    }

    # --- Optional: register the hidden launcher to run at login.
    if ($Startup) {
        $vbs        = Join-Path $BinDir 'net-quota-hidden.vbs'
        $startupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
        New-Item -ItemType Directory -Force -Path $startupDir | Out-Null
        $lnk = Join-Path $startupDir 'NetQuota.lnk'
        $wsh = New-Object -ComObject WScript.Shell
        $sc  = $wsh.CreateShortcut($lnk)
        $sc.TargetPath       = 'wscript.exe'
        $sc.Arguments        = '"' + $vbs + '"'
        $sc.WorkingDirectory = $RepoRoot
        $sc.Description      = 'NetQuota (hidden) auto-start'
        $sc.Save()
        Write-Host "Installed hidden auto-start: $lnk" -ForegroundColor Green

        # Remove any legacy visible auto-start shortcuts.
        foreach ($legacy in @('NetQuota Auto-Start.lnk', 'NetQuota Agent.lnk')) {
            $old = Join-Path $startupDir $legacy
            if (Test-Path $old) { Remove-Item -Force $old; Write-Host "Removed old visible shortcut: $old" }
        }
    }

    Write-Host "Role set to '$r'." -ForegroundColor Green
    Write-Host 'Open a NEW cmd window (or sign out/in), then run: net-quota run' -ForegroundColor Cyan
}

function Show-Help {
    Write-Host @'
net-quota - run/stop/status the NetQuota stack

  net-quota run               Start components and keep them alive (hidden)
  net-quota run --show        Same, but with visible component windows
  net-quota run --once        Start whatever is missing, then exit
  net-quota stop              Stop every NetQuota component
  net-quota status            Show what is running
  net-quota install           Add this command to PATH and record the role
  net-quota install -Startup  Also auto-start (hidden) at login
  net-quota help              This help

Components write logs to %ProgramData%\NetQuota\logs
'@
}

switch ($Command) {
    'run'     { Invoke-Run }
    'stop'    { Stop-NetQuota; Write-Host 'Stopped.' -ForegroundColor Green }
    'status'  { Show-Status }
    'install' { Invoke-Install }
    'help'    { Show-Help }
}
