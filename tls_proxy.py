"""双协议入口代理：同一个端口上 localhost 说 HTTP、LAN 说 HTTPS。

背景：cheroot 在单一连接管理线程里执行 TLS 握手，任何一个卡死的握手
（校园网客户端中途放弃、扫描器探测）都会堵死全站 accept，最长卡满
socket 超时——2026-10 在校园网实测复现（CPU 空闲、localhost 探测
连续超时约 40 秒后自愈）。本模块只用标准库实现：

- accept 线程只做 accept 与首字节嗅探（TLS ClientHello 首字节为 0x16，
  HTTP 方法首字节是 ASCII 字母，二者不可能混淆），绝不触碰 TLS；
- 每个连接由独立线程完成握手并把字节流原样转发给回环上的 waitress，
  卡死的握手最多占用自己的线程（10 秒超时回收），不影响任何其他连接；
- 回环地址两种协议都放行（localhost 走 HTTP）；外部地址说纯 HTTP
  一律拒绝并提示改用 HTTPS（安全底线：LAN 必须加密）。

所有依赖由 uv 安装，本模块本身不依赖任何第三方包。
"""

from __future__ import annotations

import select
import socket
import ssl
import threading

LISTEN_HOST = "0.0.0.0"
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 5001
HANDSHAKE_TIMEOUT = 10   # 首字节嗅探 + TLS 握手的总时限（秒）
IDLE_TIMEOUT = 75        # 已建立连接的空闲回收（秒），浏览器 keep-alive 到期自动重连
BUF_SIZE = 65536
BACKLOG = 256

_LOCAL_ADDRS = {"127.0.0.1", "::1"}
_TLS_HANDSHAKE_BYTE = b"\x16"

_FORBIDDEN_BODY = (
    "局域网访问必须使用 HTTPS：https://<服务器地址>（首次访问需在浏览器确认证书例外）\n"
).encode("utf-8")
_FORBIDDEN = (
    b"HTTP/1.1 403 Forbidden\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"Connection: close\r\n"
    b"\r\n"
    + _FORBIDDEN_BODY
)


def _make_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_path, key_path)
    return context


def _pump(left: socket.socket, right: socket.socket) -> None:
    """双向转发直到任一端关闭或空闲超时。"""
    pair = (left, right)
    try:
        while True:
            readable, _, _ = select.select(pair, [], [], IDLE_TIMEOUT)
            if not readable:
                return
            for source in readable:
                data = source.recv(BUF_SIZE)
                if not data:
                    return
                (right if source is left else left).sendall(data)
    except OSError:
        pass
    finally:
        for sock in pair:
            try:
                sock.close()
            except OSError:
                pass


def _handle(client: socket.socket, peer: str, context: ssl.SSLContext,
            upstream: tuple[str, int]) -> None:
    try:
        client.settimeout(HANDSHAKE_TIMEOUT)
        first = client.recv(1, socket.MSG_PEEK)
        if first == _TLS_HANDSHAKE_BYTE:
            conn = context.wrap_socket(client, server_side=True)
        elif peer in _LOCAL_ADDRS:
            conn = client  # 回环纯 HTTP 直通
        else:
            client.sendall(_FORBIDDEN)
            client.close()
            return
        conn.settimeout(None)
        _pump(conn, socket.create_connection(upstream))
    except (OSError, ssl.SSLError):
        try:
            client.close()
        except OSError:
            pass


def serve(port: int, cert_path: str, key_path: str,
          upstream: tuple[str, int] = (UPSTREAM_HOST, UPSTREAM_PORT)) -> None:
    """在 0.0.0.0:port 上提供双协议入口（阻塞，运行于主线程）。"""
    context = _make_context(cert_path, key_path)
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((LISTEN_HOST, port))
    listener.listen(BACKLOG)
    while True:
        client, (peer, _) = listener.accept()
        threading.Thread(
            target=_handle, args=(client, peer, context, upstream), daemon=True
        ).start()
