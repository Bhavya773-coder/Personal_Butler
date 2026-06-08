@echo off
echo ============================================
echo  JARVIS Core — Backend Installation
echo ============================================

cd /d "%~dp0\..\backend"

echo.
echo [1/3] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Python dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [3/3] Installing Playwright browsers...
playwright install chromium
if errorlevel 1 (
    echo WARNING: Playwright browser install failed. Run manually: playwright install chromium
)

echo.
echo ============================================
echo  Backend installation complete!
echo ============================================
echo.
echo Next steps:
echo   1. Install Ollama from https://ollama.com
echo   2. Run: ollama pull llama3.2
echo   3. Run: scripts\start_dev.bat
echo.
pause
