@echo off
echo ========================================
echo   Plagiarism Remover - Starting...
echo ========================================
echo.

echo [1/2] Starting backend API...
cd /d "%~dp0backend"
start "Backend" cmd /k "uvicorn main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak >nul

echo [2/2] Opening app in browser...
start "" "http://127.0.0.1:8000/app/index.html"

echo.
echo App is running at: http://127.0.0.1:8000/app/index.html
echo Close the backend window to stop the server.
pause
