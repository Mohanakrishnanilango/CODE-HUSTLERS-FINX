@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   GHOSTNET SSS SENTINEL - Windows Startup
echo   Side-Scan Sonar Ghost Net Detection
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

echo [1/4] Checking Python environment...
python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'" || (
    echo [ERROR] Python 3.10 or higher is required.
    pause
    exit /b 1
)

echo [2/4] Setting up environment configuration...
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo   Created .env from .env.example
    ) else (
        echo   Warning: .env.example not found.
    )
)

echo [3/4] Initializing database schema...
python -c "from app.database.session import init_db; init_db(); print('  Database schema ready.')"

echo [4/4] Starting server...
echo.
echo   Landing:    http://localhost:8000/
echo   Dashboard:  http://localhost:8000/dashboard
echo   Batch:      http://localhost:8000/batch
echo   API Docs:   http://localhost:8000/docs
echo   Health:     http://localhost:8000/health
echo.
echo   Press Ctrl+C to stop the server.
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
