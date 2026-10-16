#!/bin/bash
# 团校积分系统 - 服务器状态

PID_FILE="server.pid"

echo "========================================"
echo "团校积分系统 - 服务器状态"
echo "========================================"
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "状态: [未运行]"
    echo ""
    exit 0
fi

SERVER_PID=$(cat "$PID_FILE")

if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "状态: [运行中]"
    echo "PID: $SERVER_PID"
    echo "日志文件: server.log"
    echo ""
    echo "查看日志: ./logs.sh"
    echo "停止服务器: ./stop_server.sh"
    echo ""
else
    echo "状态: [未运行] （进程不存在）"
    echo "PID文件存在但进程已停止"
    echo ""
fi
