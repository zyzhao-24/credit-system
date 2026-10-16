#!/bin/bash
# 团校积分系统 - 查看日志

LOG_FILE="server.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "日志文件不存在: $LOG_FILE"
    exit 1
fi

echo "========================================"
echo "团校积分系统 - 服务器日志"
echo "========================================"
echo ""
echo "按 Ctrl+C 退出"
echo ""

tail -f "$LOG_FILE"
