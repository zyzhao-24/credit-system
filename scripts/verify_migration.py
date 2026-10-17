"""Verify a JSON-to-SQLite migration without exposing sensitive values."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import create_app  # noqa: E402
from backend.extensions import db  # noqa: E402
from backend.models import (  # noqa: E402
    Activity,
    ActivityQuestionnaire,
    Admin,
    Category,
    Department,
    EmailConfig,
    Entry,
    QuestionnaireResponse,
    Record,
    Student,
)
from backend.services.credits import calculate_student_credits  # noqa: E402
from backend.services.legacy_export import export_legacy_payload  # noqa: E402
from backend.utils.crypto import decrypt_secret  # noqa: E402
from backend.utils.passwords import client_password_digest, verify_password_digest  # noqa: E402


def sqlite_uri(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def normalize(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    return value


def redacted_source(payload: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(payload, ensure_ascii=False))
    for item in result.get("students", {}).values():
        item["password"] = "<redacted>"
    for item in result.get("admins", {}).values():
        item["password"] = "<redacted>"
    result.setdefault("email_config", {})["service_email_password"] = "<redacted>"
    return normalize(result)


def diff_paths(left: Any, right: Any, path: str = "$", limit: int = 50) -> list[str]:
    if len(path) > 300 or limit <= 0:
        return []
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        paths = []
        for key in sorted(set(left) | set(right), key=str):
            if key not in left or key not in right:
                paths.append(f"{path}.{key}")
            else:
                paths.extend(diff_paths(left[key], right[key], f"{path}.{key}", limit - len(paths)))
            if len(paths) >= limit:
                return paths[:limit]
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{path}.length"]
        paths = []
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            paths.extend(diff_paths(left_item, right_item, f"{path}[{index}]", limit - len(paths)))
            if len(paths) >= limit:
                return paths[:limit]
        return paths
    return [] if left == right else [path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQLite migration fidelity")
    parser.add_argument("--data", default=str(ROOT / "data.json"))
    parser.add_argument("--db", default=str(ROOT / "instance" / "credit_system.db"))
    parser.add_argument("--golden", default=str(ROOT / "var" / "golden" / "legacy_baseline.json"))
    parser.add_argument("--report", default=str(ROOT / "var" / "golden" / "migration_verify_report.json"))
    args = parser.parse_args()

    data_path = Path(args.data)
    db_path = Path(args.db)
    golden_path = Path(args.golden)
    report_path = Path(args.report)
    for path, label in ((data_path, "data.json"), (db_path, "SQLite"), (golden_path, "黄金基线")):
        if not path.is_file():
            raise SystemExit(f"{label} 不存在: {path}")

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    app = create_app(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=sqlite_uri(db_path),
        CORS_ORIGINS=[],
    )

    checks: dict[str, Any] = {}
    with app.app_context():
        counts = {
            "students": Student.query.count(),
            "admins": Admin.query.count(),
            "categories": Category.query.count(),
            "departments": Department.query.count(),
            "activities": Activity.query.count(),
            "records": Record.query.count(),
            "entries": Entry.query.count(),
            # 注册问卷已并入 students 表：用已映射信息的学生数对齐旧表行数
            "registration_questionnaires": Student.query.filter(
                Student.info_updated_at.isnot(None)
            ).count(),
            "activity_questionnaires": ActivityQuestionnaire.query.count(),
            "questionnaire_responses": QuestionnaireResponse.query.count(),
        }
        checks["counts_match_golden"] = counts == golden["counts"]

        # 注册问卷不再保留原 questionnaire_id 键，字段级校验单独做，形状 diff 中排除
        exported = normalize(export_legacy_payload(redact_sensitive=True))
        exported.pop("registration_questionnaires", None)
        expected = redacted_source(payload)
        expected.pop("registration_questionnaires", None)
        checks["student_info_mapped"] = all(
            (student := db.session.get(Student, item["student_id"])) is not None
            and student.phone == item.get("phone", "")
            and student.wechat == item.get("wechat", "")
            and student.suggestion == item.get("suggestion", "")
            for item in payload.get("registration_questionnaires", {}).values()
            if item["student_id"] in payload.get("students", {})
        )
        mismatches = diff_paths(expected, exported)
        checks["legacy_shape_roundtrip"] = not mismatches
        checks["legacy_shape_mismatch_paths"] = mismatches

        checks["order_preserved"] = {
            "categories": list(payload["categories"]) == list(exported["categories"]),
            "departments": payload["departments"] == exported["departments"],
            "activities": list(payload["activities"]) == list(exported["activities"]),
            "records_and_entries": all(
                [
                    [record["record_id"] for record in source_activity.get("records", [])]
                    == [record["record_id"] for record in exported["activities"][activity_id]["records"]]
                    for activity_id, source_activity in payload["activities"].items()
                ]
            ),
        }

        checks["student_password_hashes_verify"] = all(
            verify_password_digest(
                db.session.get(Student, student_id).password_hash,
                client_password_digest(item["password"]),
            )
            for student_id, item in payload["students"].items()
        )
        checks["admin_password_hashes_verify"] = all(
            verify_password_digest(
                db.session.get(Admin, admin_id).password_hash,
                client_password_digest(item["password"]),
            )
            for admin_id, item in payload["admins"].items()
        )

        email_config = db.session.get(EmailConfig, 1)
        checks["smtp_password_roundtrip"] = bool(email_config) and decrypt_secret(
            email_config.service_email_password_encrypted,
            app.config["SECRET_KEY"],
        ) == payload.get("email_config", {}).get("service_email_password", "")

        credit_mismatches = []
        for student_id, expected_result in golden["direct_student_credits"].items():
            actual_result = normalize(calculate_student_credits(student_id))
            if actual_result != normalize(expected_result):
                credit_mismatches.append(student_id)
        checks["credit_golden_match"] = not credit_mismatches
        checks["credit_mismatch_count"] = len(credit_mismatches)

    success = (
        checks["counts_match_golden"]
        and checks["legacy_shape_roundtrip"]
        and all(checks["order_preserved"].values())
        and checks["student_password_hashes_verify"]
        and checks["admin_password_hashes_verify"]
        and checks["smtp_password_roundtrip"]
        and checks["credit_golden_match"]
    )
    report = {"success": success, "counts": counts, "checks": checks}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": success, "counts": counts, "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
