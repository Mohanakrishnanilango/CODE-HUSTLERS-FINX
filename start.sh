#!/usr/bin/env bash
# GhostNet SSS Sentinel - Startup Script
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJ_DIR"

echo "============================================"
echo "  GHOSTNET SSS SENTINEL - Prototype v1.0"
echo "  Side-Scan Sonar Ghost Net Detection"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.10+."
    exit 1
fi

echo "[1/4] Checking dependencies..."
python3 -c "import fastapi, uvicorn, cv2, numpy, sqlalchemy" 2>/dev/null || {
    echo "Installing dependencies..."
    python3 -m pip install --user -r requirements.txt
}

echo "[2/4] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from .env.example"
fi

echo "[3/4] Initializing database..."
python3 -c "
from app.database.session import init_db
init_db()
print('  Database schema ready (SQLite)')
"

echo "[4/4] Starting server..."
echo ""
echo "  Dashboard:  http://localhost:8000/dashboard"
echo "  API Docs:   http://localhost:8000/docs"
echo "  Health:     http://localhost:8000/health"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
