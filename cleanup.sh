#!/bin/bash
# 团校积分系统 - 强制清理
# 只停止本项目 server.pid 记录的进程，不再 pkill 全部 python 进程

echo "========================================"
echo "Tuanxiao Credit System - Force Cleanup"
echo "========================================"
echo ""
echo "This will:"
echo "- Stop ONLY this project's server process (PID from server.pid)"
echo "- Remove server.pid file"
echo "- Remove server.log file"
echo ""

read -p "Are you sure you want to continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "[INFO] Cleanup cancelled"
    exit 0
fi

echo ""
if [ -f "server.pid" ]; then
    SERVER_PID=$(cat server.pid)
    echo "[INFO] Stopping server process - PID: $SERVER_PID"
    if kill $SERVER_PID 2>/dev/null; then
        sleep 2
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            kill -9 $SERVER_PID 2>/dev/null
        fi
        echo "[SUCCESS] Server process stopped"
    else
        echo "[INFO] Process $SERVER_PID not found or already stopped"
    fi
    rm -f server.pid
    echo "[SUCCESS] PID file removed"
else
    echo "[INFO] PID file not found - server is not running via the scripts"
fi

echo "[INFO] Removing log file..."
if [ -f "server.log" ]; then
    rm -f server.log
    echo "[SUCCESS] Log file removed"
else
    echo "[INFO] Log file not found"
fi

echo ""
echo "[SUCCESS] Cleanup completed"
echo ""
