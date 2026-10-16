"""Dump the SQLite database in legacy data.json shape for audit/rollback review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import create_app  # noqa: E402
from backend.services.legacy_export import export_legacy_payload  # noqa: E402


def sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump SQLite as legacy-shaped JSON")
    parser.add_argument("--db", default=str(ROOT / "instance" / "credit_system.db"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        raise SystemExit(f"数据库不存在: {db_path}")
    app = create_app(SQLALCHEMY_DATABASE_URI=sqlite_uri(db_path), CORS_ORIGINS=[])
    with app.app_context():
        payload = export_legacy_payload(redact_sensitive=True)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
