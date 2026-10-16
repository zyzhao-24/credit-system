"""Migrate legacy data.json into a new SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import create_app  # noqa: E402
from backend.extensions import db  # noqa: E402
from backend.services.legacy_import import import_legacy_payload  # noqa: E402


def sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def remove_sqlite_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate data.json to SQLite")
    parser.add_argument("--data", default=str(ROOT / "data.json"))
    parser.add_argument("--db", default=str(ROOT / "instance" / "credit_system.db"))
    parser.add_argument("--replace", action="store_true", help="replace an existing database")
    args = parser.parse_args()

    data_path = Path(args.data)
    db_path = Path(args.db)
    if not data_path.is_file():
        raise SystemExit(f"数据文件不存在: {data_path}")
    if db_path.exists() and not args.replace:
        raise SystemExit(f"数据库已存在，拒绝覆盖: {db_path}（确需覆盖请使用 --replace）")

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    secret_key = os.getenv("SECRET_KEY", "")
    if payload.get("email_config", {}).get("service_email_password") and not secret_key:
        raise SystemExit("迁移加密 SMTP 密码前必须设置 SECRET_KEY 环境变量")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    remove_sqlite_files(db_path)
    created = False
    app = create_app(
        SECRET_KEY=secret_key or "dev-only-change-me",
        SQLALCHEMY_DATABASE_URI=sqlite_uri(db_path),
        CORS_ORIGINS=[],
    )

    try:
        with app.app_context():
            db.create_all()
            counts = import_legacy_payload(payload)
            db.session.commit()
            created = True
    except Exception:
        with app.app_context():
            db.session.rollback()
        if not created:
            remove_sqlite_files(db_path)
        raise

    print(json.dumps({"database": str(db_path), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
