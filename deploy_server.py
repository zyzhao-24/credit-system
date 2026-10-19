"""
团校积分系统 - 服务器部署版本

架构（2026-10 起，全部组件由 uv 安装，无任何外部依赖）：

    localhost --HTTP--> tls_proxy(0.0.0.0:5000) --> waitress(127.0.0.1:5001) 主应用
    LAN       --HTTPS--> 〃（TLS 在每连接独立线程握手）

    本机维护台：独立 app 监听 127.0.0.1:5002，主应用不挂载维护台蓝图，
    端口级隔离，绝不对外暴露。

为何不用 cheroot 直接对外：cheroot 在单一连接管理线程里做 TLS 握手，
任何卡死的握手（校园网客户端中途放弃、扫描器探测）都会堵死全站
accept——2026-10 在校园网实测复现（CPU 空闲、localhost 探测连续
超时约 40 秒后自愈）。tls_proxy 的 accept 线程只做首字节嗅探，
卡死的握手最多占用自己的线程。

运行方式：
    set FLASK_ENV=production
    set SECRET_KEY=<随机密钥>
    python deploy_server.py
"""

import os
import sys
import socket
import threading

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

PUBLIC_PORT = int(os.environ.get('PORT', '5000'))  # 对外双协议入口
APP_PORT = 5001          # 主应用（仅回环，外部无法直连）
MAINTENANCE_PORT = 5002  # 本机维护台（仅回环，绝不对外暴露）


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
    import gen_cert
    import tls_proxy
    from waitress import serve

    # 主应用不含维护台；维护台是独立 app，跑在独立回环端口
    app = create_app(include_maintenance=False)
    maintenance_app = create_app(maintenance_only=True)

    local_ip = get_local_ip()
    # 证书不存在时自动生成自签名证书（纯 Python，无外部依赖）
    tls_available = gen_cert.ensure_cert()

    # waitress.serve 阻塞，放守护线程；主线程跑 tls_proxy 的 accept 循环
    threading.Thread(
        target=serve,
        kwargs=dict(app=app, host='127.0.0.1', port=APP_PORT,
                    threads=64, channel_timeout=300, _quiet=True),
        daemon=True,
    ).start()
    threading.Thread(
        target=serve,
        kwargs=dict(app=maintenance_app, host='127.0.0.1',
                    port=MAINTENANCE_PORT, threads=8, _quiet=True),
        daemon=True,
    ).start()

    # 由服务进程自己写入 PID，避免启动脚本误抓其它 python.exe
    with open('server.pid', 'w', encoding='utf-8') as pid_file:
        pid_file.write(str(os.getpid()))

    print("\n" + "=" * 60)
    print("Credit System Server Started")
    print("=" * 60)
    print(f"\n[localhost]")
    print(f"   学生登录:   http://localhost:{PUBLIC_PORT}/login")
    print(f"   管理员登录: http://localhost:{PUBLIC_PORT}/admin/login")
    print(f"   维护台:     http://localhost:{MAINTENANCE_PORT}/local/system (独立端口，仅本机)")
    if tls_available:
        print(f"\n[LAN]（必须使用 HTTPS）")
        print(f"   Student: https://{local_ip}:{PUBLIC_PORT}/login")
        print(f"   Admin:   https://{local_ip}:{PUBLIC_PORT}/admin/login")
    else:
        print(f"\n[严重警告] 自签名证书不可用，LAN 入口未启动")
        print(f"   安全底线：LAN 必须 HTTPS，不允许回退明文；")
        print(f"   请运行 uv run python gen_cert.py 排查证书生成后重启")
    print(f"\n[Tips]")
    print(f"   - 内部结构: tls_proxy(:{PUBLIC_PORT} 双协议) -> 主应用(127.0.0.1:{APP_PORT})")
    print(f"   - LAN 说 HTTP 会被拒绝；localhost 请用 http://")
    print(f"   - Press Ctrl+C to stop the server")
    print("=" * 60 + "\n", flush=True)

    try:
        if tls_available:
            tls_proxy.serve(PUBLIC_PORT, TLS_CERT, TLS_KEY,
                            upstream=('127.0.0.1', APP_PORT))
        else:
            # fail-closed：宁可 LAN 不可用也不明文；localhost 服务保持运行
            threading.Event().wait()
    finally:
        try:
            os.remove('server.pid')
        except OSError:
            pass
