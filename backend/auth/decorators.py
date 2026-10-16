"""JWT authorization decorators used by API blueprints."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import current_app, g, jsonify, request

from backend.auth.jwt import TokenError, decode_token


F = TypeVar("F", bound=Callable[..., Any])


def _unauthorized(message: str, status: int = 401):
    return jsonify({"success": False, "message": message}), status


def _load_identity() -> dict[str, Any] | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    if getattr(g, "current_identity_token", None) == token and hasattr(g, "current_identity"):
        return g.current_identity
    try:
        g.current_identity = decode_token(token, current_app.config["SECRET_KEY"])
        g.current_identity_token = token
        return g.current_identity
    except TokenError:
        return None


def require_auth(view: F) -> F:
    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = _load_identity()
        if identity is None:
            return _unauthorized("未登录或登录已过期")
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_student(view: F) -> F:
    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = _load_identity()
        if identity is None:
            return _unauthorized("未登录或登录已过期")
        if identity.get("user_type") != "student":
            return _unauthorized("无权限", 403)
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_admin(view: F) -> F:
    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = _load_identity()
        if identity is None:
            return _unauthorized("未登录或登录已过期")
        if identity.get("user_type") != "admin":
            return _unauthorized("无权限", 403)
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_system_admin(view: F) -> F:
    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = _load_identity()
        if identity is None:
            return _unauthorized("未登录或登录已过期")
        if identity.get("user_type") != "admin":
            return _unauthorized("无权限", 403)
        if identity.get("role") != "system_admin":
            return _unauthorized("仅系统管理员可以执行此操作", 403)
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
