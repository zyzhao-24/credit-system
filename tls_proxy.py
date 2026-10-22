"""双协议入口代理：同一个端口上 localhost 说 HTTP、LAN 说 HTTPS。

背景：cheroot 在单一连接管理线程里执行 TLS 握手，任何一个卡死的握手
（校园网客户端中途放弃、扫描器探测）都会堵死全站 accept，最长卡满
socket 超时——2026-10 在校园网实测复现（CPU 空闲、localhost 探测
连续超时约 40 秒后自愈）。本模块只做轻量协议处理：

- accept 线程只做 accept 与首字节嗅探（TLS ClientHello 首字节为 0x16，
  HTTP 方法首字节是 ASCII 字母，二者不可能混淆），绝不触碰 TLS；
- 每个连接由独立线程完成握手并转发，卡死的握手最多占用自己的线程
  （10 秒超时回收），不影响任何其他连接；
- 回环地址两种协议都放行（localhost 走 HTTP）；外部地址说纯 HTTP
  一律拒绝并提示改用 HTTPS（安全底线：LAN 必须加密）；
- 客户端→上游方向用 h11 解析每条请求，覆盖写入 X-Forwarded-For /
  X-Real-IP 为真实来源地址（客户端自带的伪造值一律剥除），上游→客户端
  方向保持原始字节转发。应用侧配合 ProxyFix 即可恢复真实客户端 IP，
  限速/审计/日志都依赖它。

依赖：h11（PyPI 纯 Python，由 uv 安装）；其余均为标准库。
"""

from __future__ import annotations

import select
import socket
import ssl
import threading

import h11

LISTEN_HOST = "0.0.0.0"
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 5001
HANDSHAKE_TIMEOUT = 10   # 首字节嗅探 + TLS 握手的总时限（秒）
IDLE_TIMEOUT = 75        # 已建立连接的空闲回收（秒），浏览器 keep-alive 到期自动重连
BUF_SIZE = 65536
BACKLOG = 256
# 并发连接上限：每连接一个线程，超限直接拒绝，防止慢连接耗尽线程/内存
MAX_CONNECTIONS = 512

_LOCAL_ADDRS = {"127.0.0.1", "::1"}
_TLS_HANDSHAKE_BYTE = b"\x16"
# 转发前剥除客户端自带的伪造来源头，随后以真实 peer 重写
_STRIPPED_HEADERS = frozenset({b"x-forwarded-for", b"x-real-ip"})

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


class _RequestRewriter:
    """把客户端字节流解析成 h11 事件，逐条请求改写来源头后再序列化。

    解析侧是 SERVER 模式；序列化侧每条请求新建一个 CLIENT 模式连接，
    因此无需处理跨请求的 keep-alive 状态复用。SERVER 状态机在需要
    "先发响应才能收下一条请求"（keep-alive 顺序请求）或 100-continue
    时会进入 PAUSED——我们不是真的服务器，真实响应走上游→客户端的原始
    回传路径，这里只喂一个假响应把状态机推进下去。
    """

    def __init__(self, peer: str) -> None:
        self._parser = h11.Connection(h11.SERVER)
        self._peer = peer.encode()
        self._serializer: h11.Connection | None = None

    def feed(self, data: bytes) -> list[bytes]:
        self._parser.receive_data(data)
        chunks: list[bytes] = []
        while True:
            event = self._parser.next_event()
            if event is h11.NEED_DATA:
                break
            if event is h11.PAUSED:
                self._unpause()
                continue
            if isinstance(event, h11.Request):
                self._serializer = h11.Connection(h11.CLIENT)
                headers = [
                    (name, value)
                    for name, value in event.headers
                    if name.lower() not in _STRIPPED_HEADERS
                ]
                headers.append((b"x-forwarded-for", self._peer))
                headers.append((b"x-real-ip", self._peer))
                chunks.append(
                    self._serializer.send(
                        h11.Request(
                            method=event.method,
                            target=event.target,
                            headers=headers,
                        )
                    )
                )
            elif isinstance(event, (h11.Data, h11.EndOfMessage)):
                if self._serializer is not None:
                    chunks.append(self._serializer.send(event))
            elif isinstance(event, h11.ConnectionClosed):
                break
        return chunks

    def _unpause(self) -> None:
        # 状态机推进用：这些假响应的字节被丢弃，真实响应由 waitress 直接回传
        if self._parser.they_are_waiting_for_100_continue:
            self._parser.send(h11.InformationalResponse(status_code=100, headers=[]))
        else:
            self._parser.send(
                h11.Response(status_code=200, headers=[(b"content-length", b"0")])
            )
            self._parser.send(h11.EndOfMessage())
            self._parser.start_next_cycle()


def _pump(left: socket.socket, right: socket.socket, peer: str) -> None:
    """双向转发直到任一端关闭或空闲超时。

    left=客户端、right=上游。客户端→上游经过 _RequestRewriter 改写来源头；
    上游→客户端原样转发。
    """
    rewriter = _RequestRewriter(peer)
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
                if source is right:
                    left.sendall(data)
                else:
                    for chunk in rewriter.feed(data):
                        right.sendall(chunk)
    except (OSError, h11.LocalProtocolError):
        # h11 解析失败（非法/罕见请求形态）按连接级故障处理：关闭本条连接，
        # 不影响其他连接；客户端重试即可
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
        _pump(conn, socket.create_connection(upstream), peer)
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
    slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def guarded_handle(client: socket.socket, peer: str) -> None:
        try:
            _handle(client, peer, context, upstream)
        finally:
            slots.release()

    while True:
        client, (peer, _) = listener.accept()
        if not slots.acquire(blocking=False):
            client.close()
            continue
        threading.Thread(
            target=guarded_handle, args=(client, peer), daemon=True
        ).start()
