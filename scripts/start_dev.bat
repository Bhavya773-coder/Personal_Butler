@echo off
echo ============================================
echo  JARVIS Core — Starting Development
echo ============================================

:: Check Ollama
echo.
echo Checking Ollama status...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: Ollama is not running!
    echo Start Ollama first, or run: ollama serve
    echo.
)

:: Start Backend
echo.
echo [1/2] Starting FastAPI backend on port 8000...
cd /d "%~dp0\..\backend"
start "JARVIS Backend" cmd /k "call venv\Scripts\activate.bat && python main.py"

:: Wait for backend to start
echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

:: Start Frontend
echo.
echo [2/2] Starting Electron + Vite frontend...
cd /d "%~dp0\..\app"
start "JARVIS Frontend" cmd /k "npm run electron:dev"

echo.
echo ============================================
echo  JARVIS Core is starting!
echo ============================================
echo.
echo  Backend: http://localhost:8000
echo  Frontend: http://localhost:5173
echo  Health: http://localhost:8000/health
echo.
echo  Press Ctrl+C in each window to stop.
echo ============================================
