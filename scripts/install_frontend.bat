@echo off
echo ============================================
echo  JARVIS Core — Frontend Installation
echo ============================================

cd /d "%~dp0\..\app"

echo.
echo [1/1] Installing Node.js dependencies...
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed. Install Node.js 18+ from nodejs.org
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Frontend installation complete!
echo ============================================
echo.
pause
