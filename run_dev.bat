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

echo [INFO] Starting backend  (http://localhost:5000) ...
start "NetWatch Backend" cmd /k "cd /d "%ROOT%" && venv\Scripts\python.exe run.py"

echo [INFO] Starting frontend dev server (http://localhost:5173) ...
start "NetWatch Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo.
echo NetWatch is starting. Backend: http://localhost:5000  Frontend: http://localhost:5173
echo Close both windows or press Ctrl+C in each to stop.
endlocal