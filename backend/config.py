"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _database_uri() -> str:
    """DATABASE_URL 里的相对 sqlite 路径一律按项目根目录解析。

    Flask-SQLAlchemy 会把相对 sqlite 路径解析到 instance_path 下，
    导致 `sqlite:///instance/credit_system.db` 变成 instance/instance/...
    在这里统一锚定到 BASE_DIR，避免歧义。
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        return _sqlite_uri(BASE_DIR / "instance" / "credit_system.db")
    prefix = "sqlite:///"
    if url.startswith(prefix):
        path = Path(url[len(prefix):])
        if not path.is_absolute():
            path = BASE_DIR / path
        return _sqlite_uri(path)
    return url


class Config:
    """Default configuration suitable for local development."""

    ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 5}}
    JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", "43200"))
    # 登录/动态码防爆破限速（按账号计失败次数，超限返回 429）
    LOGIN_FAIL_MAX_PER_MINUTE = int(os.getenv("LOGIN_FAIL_MAX_PER_MINUTE", "5"))
    LOGIN_FAIL_MAX_PER_HOUR = int(os.getenv("LOGIN_FAIL_MAX_PER_HOUR", "20"))
    OTP_FAIL_MAX_PER_TICKET = int(os.getenv("OTP_FAIL_MAX_PER_TICKET", "5"))
    OTP_FAIL_MAX_PER_MINUTE = int(os.getenv("OTP_FAIL_MAX_PER_MINUTE", "10"))
    # 第二层：单 IP 全账号失败限速（防撞库扫号；判定在校验之前，见 api/auth.py）
    LOGIN_IP_FAIL_MAX_PER_MINUTE = int(os.getenv("LOGIN_IP_FAIL_MAX_PER_MINUTE", "50"))
    LOGIN_IP_FAIL_MAX_PER_HOUR = int(os.getenv("LOGIN_IP_FAIL_MAX_PER_HOUR", "300"))
    # OTP 票据签发限速：正确密码每分钟最多领 3 张票，防"取票→试 N 次→再取票"循环
    OTP_TICKET_MAX_PER_MINUTE = int(os.getenv("OTP_TICKET_MAX_PER_MINUTE", "3"))
    # 第三层：全站失败桶——全站登录失败超阈值时对所有失败响应加延迟（不拒绝，
    # 避免攻击者通过刷失败把站点打成 429 的 DoS）
    LOGIN_GLOBAL_FAIL_PER_MINUTE = int(os.getenv("LOGIN_GLOBAL_FAIL_PER_MINUTE", "120"))
    LOGIN_GLOBAL_FAIL_DELAY_SECONDS = float(os.getenv("LOGIN_GLOBAL_FAIL_DELAY_SECONDS", "2"))
    # 限速字典键上限：防伪造大量不同来源撑爆内存（超限丢最旧的键）
    RATE_LIMIT_MAX_KEYS = int(os.getenv("RATE_LIMIT_MAX_KEYS", "100000"))
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    JSON_AS_ASCII = False


class ProductionConfig(Config):
    """Production configuration requires an explicit secret key."""

    ENV = "production"
    # 生产环境前后端同源部署，默认不开放任何跨域来源；
    # 仅在显式设置 CORS_ORIGINS 环境变量时才放行。
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]

    def __init__(self) -> None:
        if not os.getenv("SECRET_KEY"):
            raise RuntimeError("生产环境必须设置 SECRET_KEY 环境变量")
        self.SECRET_KEY = os.environ["SECRET_KEY"]
