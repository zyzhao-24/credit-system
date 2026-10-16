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

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found"
    exit 1
fi

# Check Waitress
if ! python3 -c "import waitress" &> /dev/null; then
    echo "[INFO] Installing Waitress..."
    pip3 install waitress
fi

# Start server
echo "[INFO] Starting server..."
export BACKGROUND_MODE=1
nohup python3 deploy_server.py > $LOG_FILE 2>&1 &
SERVER_PID=$!

# Wait
sleep 2

# Check if running
if ! ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "[ERROR] Failed to start server"
    echo "Check server.log for details"
    exit 1
fi

# Save PID
echo $SERVER_PID > "$PID_FILE"

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
echo "Access: http://localhost:5000"
echo ""
