"""JWT authorization decorators used by API blueprints."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import current_app, g, jsonify, request

from backend.auth.jwt import TokenError, decode_token


F = TypeVar("F", bound=Callable[..., Any])

# 一次性票据（OTP 第二步、OTP 绑定确认）不是访问令牌，不做账号级校验
_TICKET_ROLES = frozenset({"otp_pending", "otp_bind_pending"})

# 初始密码未修改（password_reset_required）时仅放行这些端点
_PASSWORD_RESET_ALLOWED_PATHS = frozenset(
    {
        "/api/auth/me",
        "/api/auth/logout",
        "/api/logout",
        "/api/student/change_password",
        "/api/admin/change_password",
    }
)


def _unauthorized(message: str, status: int = 401, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _load_identity() -> dict[str, Any] | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    # 不做跨调用缓存：吊销检查（token_version）必须在每次校验时都回查数据库，
    # 缓存在共享 app 上下文的场景（如测试）会让已吊销的令牌继续放行
    try:
        identity = decode_token(token, current_app.config["SECRET_KEY"])
    except TokenError:
        return None

    if identity.get("role") not in _TICKET_ROLES:
        # 访问令牌必须回查账号：不存在或令牌版本过期（改密/重置/登出）一律作废
        from backend.extensions import db
        from backend.models import Admin, Student

        model = Student if identity.get("user_type") == "student" else Admin
        account = db.session.get(model, identity.get("sub", ""))
        if account is None or account.token_version != identity.get("tv", -1):
            return None
        g.current_account = account

    g.current_identity = identity
    g.current_identity_token = token
    return identity


def _password_reset_block():
    """强制首次改密：带初始密码标记的账号只能访问改密/登出等少数端点。"""
    account = getattr(g, "current_account", None)
    if (
        account is not None
        and getattr(account, "password_reset_required", False)
        and request.path not in _PASSWORD_RESET_ALLOWED_PATHS
    ):
        return _unauthorized(
            "首次登录请先修改初始密码",
            403,
            password_reset_required=True,
        )
    return None


def require_auth(view: F) -> F:
    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = _load_identity()
        if identity is None:
            return _unauthorized("未登录或登录已过期")
        blocked = _password_reset_block()
        if blocked is not None:
            return blocked
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
        blocked = _password_reset_block()
        if blocked is not None:
            return blocked
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
        blocked = _password_reset_block()
        if blocked is not None:
            return blocked
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
        blocked = _password_reset_block()
        if blocked is not None:
            return blocked
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
