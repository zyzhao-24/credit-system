#!/bin/bash
# 团校积分系统 - 停止服务器脚本

PID_FILE="server.pid"

echo "========================================"
echo "团校积分系统 - 停止服务器"
echo "========================================"
echo ""

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "[提示] 服务器未运行（找不到PID文件）"
    exit 0
fi

# 读取PID
SERVER_PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ! ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "[提示] 服务器未运行（进程不存在）"
    rm -f "$PID_FILE"
    exit 0
fi

# 停止服务器
echo "[停止] 正在停止服务器 (PID: $SERVER_PID)..."
kill $SERVER_PID

# 等待进程结束
sleep 2

# 检查是否成功停止
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "[警告] 进程未响应，强制停止..."
    kill -9 $SERVER_PID
    sleep 1
fi

# 清理PID文件
rm -f "$PID_FILE"

echo "[完成] 服务器已停止"
echo ""
