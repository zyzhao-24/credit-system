#!/bin/bash
# Tuanxiao Credit System - Start Server

PID_FILE="server.pid"
LOG_FILE="server.log"

echo "========================================"
echo "Tuanxiao Credit System - Start Server"
echo "========================================"
echo ""

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "[ERROR] Server already running - PID: $OLD_PID"
        echo "Run ./stop_server.sh first"
        echo ""
        exit 1
    fi
    rm -f "$PID_FILE"
fi

# Check Python (prefer the project virtualenv)
PYTHON=python3
if [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
fi
if ! command -v "$PYTHON" &> /dev/null && [ ! -f "$PYTHON" ]; then
    echo "[ERROR] Python3 not found"
    exit 1
fi

# Check dependencies with the same interpreter that will run the server
if ! "$PYTHON" -c "import waitress, flask, flask_sqlalchemy, flask_cors, flask_migrate, jwt, cryptography, dotenv, openpyxl" &> /dev/null; then
    echo "[INFO] Syncing dependencies with uv..."
    uv sync || { echo "[ERROR] Dependency install failed - install uv first: https://docs.astral.sh/uv/"; exit 1; }
    # uv sync creates .venv; switch to it if the script started without one
    if [ -f ".venv/Scripts/python.exe" ]; then
        PYTHON=".venv/Scripts/python.exe"
    elif [ -f ".venv/bin/python" ]; then
        PYTHON=".venv/bin/python"
    fi
fi

# Build frontend if missing (uses uv-managed Node.js, no system Node needed)
if [ ! -f frontend/dist/index.html ]; then
    echo "[INFO] Building frontend with bundled Node.js..."
    "$PYTHON" build_frontend.py || { echo "[ERROR] Frontend build failed"; exit 1; }
fi

# Load configuration from .env into environment variables
if [ ! -f .env ]; then
    echo "[ERROR] .env not found - copy .env.example to .env and fill it in"
    exit 1
fi
set -a
. ./.env
set +a

# SECRET_KEY is required in production mode
if [ -z "$SECRET_KEY" ]; then
    echo "[ERROR] SECRET_KEY is missing in .env or the environment"
    echo "        Add SECRET_KEY=<random-long-string> to .env"
    exit 1
fi

# Start server (deploy_server.py writes its own PID file)
echo "[INFO] Starting server..."
export BACKGROUND_MODE=1
rm -f "$PID_FILE"
nohup "$PYTHON" deploy_server.py > $LOG_FILE 2>&1 &

# Wait for the server process to write its PID
SERVER_PID=""
for i in $(seq 1 10); do
    sleep 1
    if [ -f "$PID_FILE" ]; then
        SERVER_PID=$(cat "$PID_FILE")
        break
    fi
done

if [ -z "$SERVER_PID" ] || ! ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "[ERROR] Failed to start server"
    echo "Check server.log for details"
    exit 1
fi

echo ""
echo "========================================"
echo "[SUCCESS] Server started"
echo "========================================"
echo ""
echo "PID: $SERVER_PID"
echo "Log: $LOG_FILE"
echo ""
echo "Commands:"
echo "  ./status.sh - Check status"
echo "  ./logs.sh   - View logs"
echo "  ./stop_server.sh - Stop server"
echo ""
echo "Localhost: http://localhost:5000/login  and  http://localhost:5000/admin/login"
echo "LAN:       https://SERVER_IP:5000/login  (HTTPS required)"
echo "Console:   http://localhost:5002/local/system"
echo ""
