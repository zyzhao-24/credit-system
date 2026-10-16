"""
团校积分系统 - 服务器部署版本

这是一个生产环境部署脚本，使用 Waitress WSGI 服务器
比 Flask 自带的开发服务器更稳定、安全、高性能

安装依赖：
pip install waitress

运行方式：
python deploy_server.py

或者使用 gunicorn (Linux):
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""

import sys
import os

# 如果通过后台脚本启动，重定向输出到日志文件
if os.environ.get('BACKGROUND_MODE') == '1':
    try:
        log_file = open('server.log', 'w', encoding='utf-8', buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    except PermissionError:
        # 如果文件被占用，尝试追加模式
        try:
            log_file = open('server.log', 'a', encoding='utf-8', buffering=1)
            sys.stdout = log_file
            sys.stderr = log_file
        except:
            # 如果还是失败，就不重定向
            pass

from waitress import serve
from app import app, ADMIN_LOGIN_PATH
import socket

def get_local_ip():
    """获取本机IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

if __name__ == '__main__':
    # 确保 Flask 配置正确（必须在启动前设置）
    app.config.update(
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=False,  # HTTP 环境设为 False
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_DOMAIN=None,  # 关键！允许在任何域名（包括 IP）下工作
        SESSION_COOKIE_NAME='session',
        PERMANENT_SESSION_LIFETIME=3600,  # Session 有效期 1 小时
        SESSION_REFRESH_EACH_REQUEST=True,  # 每次请求刷新 session
    )
    
    host = '0.0.0.0'  # 监听所有网络接口
    port = 5000
    
    local_ip = get_local_ip()
    
    print("\n" + "="*60)
    print("Credit System Server Started")
    print("="*60)
    print(f"\nStudent Login: http://localhost:5000")
    print(f"Admin Login: http://localhost:5000/{ADMIN_LOGIN_PATH}")
    print("\n" + "="*60 + "\n")
    print(f"\n[Student Login]")
    print(f"   Local: http://localhost:{port}")
    print(f"   LAN: http://{local_ip}:{port}")
    print(f"\n[Admin Login]")
    print(f"   Local: http://localhost:{port}/{ADMIN_LOGIN_PATH}")
    print(f"   LAN: http://{local_ip}:{port}/{ADMIN_LOGIN_PATH}")
    print(f"\n[Tips]")
    print(f"   - Student Login: Access the homepage directly")
    print(f"   - Admin Login: Use the admin login URL above")
    print(f"   - Supports access via IP address or localhost")
    print(f"   - Press Ctrl+C to stop the server")
    print("\n" + "="*60 + "\n")
    print(flush=True)
    
    # 使用 Waitress 启动服务器
    # threads: 线程数，根据服务器性能调整
    # channel_timeout: 通道超时时间
    # url_scheme: 设置为 http（重要！）
    serve(app, host=host, port=port, threads=4, channel_timeout=300, url_scheme='http')
