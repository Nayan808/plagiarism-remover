@echo off
echo ========================================
echo   Plagiarism Remover - Setup
echo ========================================
echo.

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Python packages...
cd /d "%~dp0backend"
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install packages.
    pause
    exit /b 1
)

echo.
echo [3/3] Pulling Ollama model (mistral)...
echo This downloads ~4 GB. Make sure Ollama is running first.
ollama pull mistral
if errorlevel 1 (
    echo WARNING: Could not pull mistral. Make sure Ollama is installed and running.
    echo Download Ollama from: https://ollama.com
)

echo.
echo ========================================
echo   Setup complete! Run start.bat to launch.
echo ========================================
pause
