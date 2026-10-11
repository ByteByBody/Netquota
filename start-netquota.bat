@echo off
REM NetQuota Auto-Start - launches backend, dashboard, and agent
REM Place a shortcut to this file in shell:startup to run on login

set PROJECT_ROOT=C:\Users\me_meansnothing\projects\netquota
set VENV=%PROJECT_ROOT%\server\.venv

REM --- Backend ---
start "NetQuota Backend" cmd /k "
    cd /d %PROJECT_ROOT%\server
    call %VENV%\Scripts\activate.bat
    set NETQUOTA_DATABASE_URL=sqlite+aiosqlite:///./netquota.db
    set NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD=changeme
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"

REM Wait a moment for backend to be ready
timeout /t 3 /nobreak >nul

REM --- Dashboard ---
start "NetQuota Dashboard" cmd /k "
    cd /d %PROJECT_ROOT%\apps\dashboard
    npm run dev
"

REM Wait for dashboard to compile
timeout /t 8 /nobreak >nul

REM --- Agent ---
start "NetQuota Agent" cmd /k "
    cd /d %PROJECT_ROOT%\agents\desktop
    call %VENV%\Scripts\activate.bat
    set NETQUOTA_INTERVAL_SECONDS=5
    netquota-agent run
"

echo All three components started in separate windows.
echo Close this window when done.
pause