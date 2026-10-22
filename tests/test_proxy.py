"""tls_proxy 的 h11 请求改写器单元测试（纯字节喂入，不起 socket）。"""

from __future__ import annotations

import h11

from tls_proxy import _RequestRewriter


def _parse(data: bytes) -> h11.Request:
    """把改写后的字节重新解析成 h11 事件，便于断言头部。"""
    conn = h11.Connection(h11.SERVER)
    conn.receive_data(data)
    event = conn.next_event()
    assert isinstance(event, h11.Request)
    return event


def test_forged_forwarded_headers_are_replaced():
    rewriter = _RequestRewriter("203.0.113.7")
    raw = (
        b"GET /api/health HTTP/1.1\r\n"
        b"Host: example.local\r\n"
        b"X-Forwarded-For: 1.2.3.4\r\n"
        b"X-Real-IP: 5.6.7.8\r\n"
        b"Connection: keep-alive\r\n"
        b"\r\n"
    )
    chunks = rewriter.feed(raw)
    request = _parse(b"".join(chunks))
    headers = dict(request.headers)
    # 伪造值被剥除，写入真实 peer；只剩一条
    assert headers[b"x-forwarded-for"] == b"203.0.113.7"
    assert headers[b"x-real-ip"] == b"203.0.113.7"
    assert list(request.headers).count((b"x-forwarded-for", b"203.0.113.7")) == 1


def test_keep_alive_multiple_requests():
    rewriter = _RequestRewriter("10.0.0.2")
    first = rewriter.feed(b"GET /a HTTP/1.1\r\nHost: h\r\n\r\n")
    assert first  # 第一条请求已改写输出
    # keep-alive 下第二条请求到达时解析状态机会 PAUSED，改写器用假响应推进
    second = rewriter.feed(b"GET /b HTTP/1.1\r\nHost: h\r\n\r\n")
    assert second
    request = _parse(b"".join(second))
    assert request.target == b"/b"
    assert dict(request.headers)[b"x-forwarded-for"] == b"10.0.0.2"


def test_post_body_passes_through():
    rewriter = _RequestRewriter("10.0.0.3")
    body = b'{"a": 1}'
    raw = (
        b"POST /api/x HTTP/1.1\r\n"
        b"Host: h\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n"
    )
    chunks = rewriter.feed(raw) + rewriter.feed(body)
    data = b"".join(chunks)
    assert data.endswith(body)
    request = _parse(data)
    assert request.method == b"POST"
