"""Capture legacy behavior baselines without touching live data.

The script copies data.json to a temporary file, points the legacy app's global
Database object at that copy, then records deterministic outputs used later as
migration and refactoring goldens. Generated output may contain operational
data and is intentionally kept under the git-ignored var/golden directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# legacy/ holds the archived pre-refactor app; keep it importable for baselines.
sys.path.insert(0, str(ROOT / "legacy"))

from database import Database  # noqa: E402
import app as legacy_app  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def response_snapshot(response) -> dict[str, Any]:
    """Return a compact snapshot of a Flask test response."""
    snapshot: dict[str, Any] = {
        "status_code": response.status_code,
        "content_type": response.content_type,
    }
    if response.is_json:
        snapshot["json"] = response.get_json()
    else:
        body = response.get_data()
        snapshot["body_sha256"] = sha256_bytes(body)
        snapshot["body_length"] = len(body)
        disposition = response.headers.get("Content-Disposition")
        if disposition:
            snapshot["content_disposition"] = disposition
    return snapshot


def make_client(**session_values):
    legacy_app.app.config.update(TESTING=True)
    client = legacy_app.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session.update(session_values)
    return client


def capture_gets(client, paths: list[str]) -> dict[str, Any]:
    return {path: response_snapshot(client.get(path)) for path in paths}


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture legacy golden behavior")
    parser.add_argument("--data", default=str(ROOT / "data.json"), help="source data.json")
    parser.add_argument(
        "--output",
        default=str(ROOT / "var" / "golden" / "legacy_baseline.json"),
        help="git-ignored golden output path",
    )
    args = parser.parse_args()

    source = Path(args.data)
    output = Path(args.output)
    if not source.is_file():
        raise SystemExit(f"数据文件不存在: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="credit-golden-") as tmp:
        temp_data = Path(tmp) / "data.json"
        shutil.copy2(source, temp_data)
        db = Database(str(temp_data))
        legacy_app.db = db

        student_ids = sorted(db.students)
        admin_ids = sorted(db.admins)
        system_admin_id = next(
            (aid for aid in admin_ids if db.admins[aid].role == "system_admin"),
            admin_ids[0] if admin_ids else None,
        )
        normal_admin_id = next(
            (aid for aid in admin_ids if db.admins[aid].role != "system_admin"),
            None,
        )
        first_student_id = student_ids[0] if student_ids else None
        first_record_id = next(iter(db.records), None)

        baseline: dict[str, Any] = {
            "source_sha256": sha256_bytes(source.read_bytes()),
            "counts": {
                "students": len(db.students),
                "admins": len(db.admins),
                "categories": len(db.categories),
                "departments": len(db.departments),
                "activities": len(db.activities),
                "records": len(db.records),
                "entries": sum(len(record.entries) for record in db.records.values()),
                "registration_questionnaires": len(db.registration_questionnaires),
                "activity_questionnaires": len(db.activity_questionnaires),
                "questionnaire_responses": len(db.questionnaire_responses),
            },
            "direct_student_credits": {
                student_id: legacy_app.calculate_student_credits(student_id)
                for student_id in student_ids
            },
            "api": {},
        }

        if system_admin_id:
            admin_client = make_client(
                user_type="admin",
                admin_id=system_admin_id,
                admin_role="system_admin",
                admin_department="",
            )
            admin_paths = [
                "/api/admin/session_info",
                "/api/admin/students",
                "/api/admin/categories",
                "/api/admin/total_credits",
                "/api/admin/email_config",
                "/api/admin/departments",
                "/api/admin/admins",
                "/api/admin/activities",
                "/api/admin/all_students_credits",
                "/api/admin/report",
                "/api/admin/questionnaires/all",
                "/api/admin/registration_questionnaires",
            ]
            if first_record_id:
                admin_paths.append(f"/api/admin/records/{first_record_id}")
            baseline["api"]["system_admin_get"] = capture_gets(admin_client, admin_paths)
            if first_student_id:
                baseline["api"]["system_admin_post"] = {
                    "/api/query/student": response_snapshot(
                        admin_client.post("/api/query/student", json={"query": first_student_id})
                    )
                }
            baseline["api"]["system_admin_exports"] = {
                "/api/admin/students/export_csv": response_snapshot(
                    admin_client.get("/api/admin/students/export_csv")
                ),
                "/api/admin/export": response_snapshot(admin_client.get("/api/admin/export")),
                "/api/admin/questionnaires/export": response_snapshot(
                    admin_client.get("/api/admin/questionnaires/export")
                ),
                "/api/admin/registration_questionnaires/export": response_snapshot(
                    admin_client.get("/api/admin/registration_questionnaires/export")
                ),
            }

        if normal_admin_id:
            normal_client = make_client(
                user_type="admin",
                admin_id=normal_admin_id,
                admin_role=db.admins[normal_admin_id].role,
                admin_department=db.admins[normal_admin_id].department,
            )
            baseline["api"]["normal_admin_get"] = capture_gets(
                normal_client,
                [
                    "/api/admin/session_info",
                    "/api/admin/students",
                    "/api/admin/categories",
                    "/api/admin/departments",
                    "/api/admin/activities",
                    "/api/admin/report",
                ],
            )
            baseline["api"]["normal_admin_forbidden_get"] = capture_gets(
                normal_client,
                [
                    "/api/admin/total_credits",
                    "/api/admin/admins",
                    "/api/admin/all_students_credits",
                    "/api/admin/export",
                    "/api/admin/questionnaires/all",
                ],
            )

        if first_student_id:
            student_client = make_client(
                user_type="student",
                student_id=first_student_id,
                student_name=db.students[first_student_id].name,
            )
            baseline["api"]["student_get"] = capture_gets(
                student_client,
                [
                    "/api/student/my_credits",
                    "/api/student/activities",
                    "/api/student/categories",
                    "/api/student/registration_questionnaire",
                    "/api/student/questionnaires/available",
                    "/api/student/questionnaires/my_registrations",
                ],
            )

    rendered = json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "counts": baseline["counts"],
                "output_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
