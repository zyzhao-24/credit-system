"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


class Config:
    """Default configuration suitable for local development."""

    ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        _sqlite_uri(BASE_DIR / "instance" / "credit_system.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 5}}
    JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", "43200"))
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
