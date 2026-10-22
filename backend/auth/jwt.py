"""JWT issuing and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


class TokenError(Exception):
    """Base class for token validation failures."""


def issue_token(
    identity: dict[str, Any],
    secret_key: str,
    expires_seconds: int,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": identity["id"],
        "user_type": identity["user_type"],
        "role": identity.get("role", ""),
        "department": identity.get("department", ""),
        "name": identity.get("name", ""),
        # 令牌版本号：账号改密/重置/登出时自增，旧令牌随之失效
        "tv": identity.get("tv", 0),
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
        **(extra or {}),
    }
    return jwt.encode(claims, secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("登录已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("登录状态无效，请重新登录") from exc
