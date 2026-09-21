@echo off
setlocal
chcp 65001 >nul
title NetWatch Dev

set "ROOT=%~dp0"

if not exist "%ROOT%venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found at "%ROOT%venv".
    echo         Create it first:  python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    pushd "%ROOT%frontend"
    call npm install
    popd
)

rem --- Free port 5000 (kill any stale backend binding it) ---
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r "^[ ]*TCP[ ]*0.0.0.0:5000[ ]" ^| findstr LISTENING') do (
    echo [INFO] Killing stale backend process PID %%a on port 5000...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r "^[ ]*TCP[ ]*\[::\]:5000[ ]" ^| findstr LISTENING') do (
    echo [INFO] Killing stale backend process PID %%a on port 5000...
    taskkill /F /PID %%a >nul 2>&1
)

echo [INFO] Starting backend  (http://localhost:5000) ...
start "NetWatch Backend" cmd /k "cd /d "%ROOT%" && venv\Scripts\python.exe run.py"

rem --- Wait until the backend is actually accepting requests ---
set "READY="
for /l %%i in (1,1,40) do (
    >nul 2>&1 powershell.exe -NoProfile -Command "(New-Object Net.Sockets.TcpClient).Connect('127.0.0.1',5000)" && (set "READY=1" & goto :backend_ready)
    >nul 2>&1 timeout /t 1 /nobreak
)
:backend_ready
if not defined READY (
    echo [ERROR] Backend did not start on port 5000. Check the NetWatch Backend window.
) else (
    echo [OK] Backend is up on port 5000.
)

echo [INFO] Starting frontend dev server (http://localhost:5173) ...
start "NetWatch Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo.
echo NetWatch started.  Frontend: http://localhost:5173   Backend: http://localhost:5000
echo Close the two windows (or press Ctrl+C in each) to stop.
endlocal