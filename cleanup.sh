#!/bin/bash
# 团校积分系统 - 强制清理

echo "========================================"
echo "Tuanxiao Credit System - Force Cleanup"
echo "========================================"
echo ""
echo "This will:"
echo "- Kill all python processes related to deploy_server.py"
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
echo "[INFO] Killing python processes..."
pkill -f "python.*deploy_server.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "[SUCCESS] Python processes killed"
else
    echo "[INFO] No python processes found"
fi

echo "[INFO] Removing PID file..."
if [ -f "server.pid" ]; then
    rm -f server.pid
    echo "[SUCCESS] PID file removed"
else
    echo "[INFO] PID file not found"
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
