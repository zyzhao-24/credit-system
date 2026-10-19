"""
团校积分系统 - 服务器部署版本

使用 WSGI 服务器托管重构后的后端（backend.create_app），
同时服务 /api 接口与 frontend/dist 下的 React 构建产物。

TLS：启动前自动检查 instance/tls.crt 与 tls.key，不存在则自动生成自签名证书
（gen_cert.ensure_cert），随后使用 cheroot 提供 HTTPS（浏览器警告属预期）；
仅当生成失败时回退到 Waitress 的明文 HTTP。

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

# 本脚本即生产入口：强制生产配置（要求 SECRET_KEY），
# 即使 .env / 环境变量里写着 FLASK_ENV=development 也不降级
os.environ['FLASK_ENV'] = 'production'

from backend import create_app

TLS_CERT = os.path.join('instance', 'tls.crt')
TLS_KEY = os.path.join('instance', 'tls.key')


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
    # 证书不存在时自动生成自签名证书；生成失败才回退明文 HTTP
    import gen_cert

    tls_available = gen_cert.ensure_cert()
    scheme = 'https' if tls_available else 'http'

    # 由服务进程自己写入 PID，避免启动脚本误抓其它 python.exe
    with open('server.pid', 'w', encoding='utf-8') as pid_file:
        pid_file.write(str(os.getpid()))

    print("\n" + "=" * 60)
    print("Credit System Server Started")
    print("=" * 60)
    print(f"\n[Localhost]")
    print(f"   学生登录:   {scheme}://localhost:{port}/login")
    print(f"   管理员登录: {scheme}://localhost:{port}/admin/login")
    print(f"   维护台:     {scheme}://localhost:{port}/local/system (仅本机可访问)")
    print(f"\n[LAN]")
    print(f"   Student: {scheme}://{local_ip}:{port}/login")
    print(f"   Admin:   {scheme}://{local_ip}:{port}/admin/login")
    print(f"\n[Tips]")
    print(f"   - Admin login is now at the fixed path /admin/login")
    if tls_available:
        print(f"   - HTTPS 使用自签名证书，浏览器提示“不安全”属预期（高级 → 继续前往）")
    else:
        print(f"   - 当前为明文 HTTP；uv run python gen_cert.py 生成证书后重启即启用 HTTPS")
    print(f"   - Press Ctrl+C to stop the server")
    print("=" * 60 + "\n", flush=True)

    try:
        if tls_available:
            from cheroot.wsgi import Server
            from cheroot.ssl.builtin import BuiltinSSLAdapter

            server = Server((host, port), app, numthreads=32, timeout=60)
            # numthreads 不能太小：校园网客户端经常在 TLS 握手中途断开，
            # 每个卡住的握手在 timeout 秒内占用一个线程，4 线程会被瞬间耗尽
            server.max_request_body_size = 10 * 1024 * 1024
            server.ssl_adapter = BuiltinSSLAdapter(TLS_CERT, TLS_KEY)
            try:
                server.start()
            finally:
                server.stop()
        else:
            from waitress import serve

            serve(app, host=host, port=port, threads=16, channel_timeout=300, url_scheme='http')
    finally:
        try:
            os.remove('server.pid')
        except OSError:
            pass

