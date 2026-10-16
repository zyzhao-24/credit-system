"""
团校积分系统 - 服务器部署版本

使用 Waitress WSGI 服务器托管重构后的后端（backend.create_app），
同时服务 /api 接口与 frontend/dist 下的 React 构建产物。

运行方式：
    set FLASK_ENV=production
    set SECRET_KEY=<随机密钥>
    python deploy_server.py
"""

import os
import sys
import socket

# 如果通过后台脚本启动，重定向输出到日志文件
if os.environ.get('BACKGROUND_MODE') == '1':
    try:
        log_file = open('server.log', 'w', encoding='utf-8', buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    except PermissionError:
        try:
            log_file = open('server.log', 'a', encoding='utf-8', buffering=1)
            sys.stdout = log_file
            sys.stderr = log_file
        except Exception:
            pass

# 生产部署默认使用生产配置（要求 SECRET_KEY）
os.environ.setdefault('FLASK_ENV', 'production')

from waitress import serve
from backend import create_app


def get_local_ip():
    """获取本机IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


if __name__ == '__main__':
    app = create_app()

    host = '0.0.0.0'
    port = int(os.environ.get('PORT', '5000'))
    local_ip = get_local_ip()

    # 由服务进程自己写入 PID，避免启动脚本误抓其它 python.exe
    with open('server.pid', 'w', encoding='utf-8') as pid_file:
        pid_file.write(str(os.getpid()))

    print("\n" + "=" * 60)
    print("Credit System Server Started")
    print("=" * 60)
    print(f"\n[Student Login]")
    print(f"   Local: http://localhost:{port}/login")
    print(f"   LAN:   http://{local_ip}:{port}/login")
    print(f"\n[Admin Login]")
    print(f"   Local: http://localhost:{port}/admin/login")
    print(f"   LAN:   http://{local_ip}:{port}/admin/login")
    print(f"\n[Tips]")
    print(f"   - Admin login is now at the fixed path /admin/login")
    print(f"   - Press Ctrl+C to stop the server")
    print("=" * 60 + "\n", flush=True)

    try:
        serve(app, host=host, port=port, threads=4, channel_timeout=300, url_scheme='http')
    finally:
        try:
            os.remove('server.pid')
        except OSError:
            pass
