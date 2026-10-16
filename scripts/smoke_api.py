"""Read-only dual-role JWT smoke test against a migrated database.

Uses credentials from data.json to exercise the real login path, then checks
representative endpoints for each role. It performs no mutations beyond the
idempotent login-time questionnaire backfill. Run from the project root:

    .venv/Scripts/python scripts/smoke_api.py
    .venv/Scripts/python scripts/smoke_api.py --db path/to/other.db
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def digest(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(PROJECT_ROOT / "instance" / "credit_system.db"))
    parser.add_argument("--data", default=str(PROJECT_ROOT / "data.json"))
    args = parser.parse_args()

    legacy = json.loads(Path(args.data).read_text(encoding="utf-8"))
    student_id, student = next(iter(legacy["students"].items()))
    admins = legacy["admins"]
    system_id = next(aid for aid, a in admins.items() if a["role"] == "system_admin")
    normal_id = next((aid for aid, a in admins.items() if a["role"] != "system_admin"), None)

    from backend import create_app

    db_path = Path(args.db).resolve()
    app = create_app(DATABASE_URL=f"sqlite:///{db_path.as_posix()}")
    client = app.test_client()

    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {label}{(' - ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(label)

    def login(username: str, password: str, user_type: str) -> str:
        response = client.post(
            "/api/auth/token",
            data={
                "grant_type": "password",
                "username": username,
                "password": digest(password),
                "user_type": user_type,
            },
        )
        payload = response.get_json(silent=True) or {}
        check(f"token login {user_type}:{username}", response.status_code == 200 and "access_token" in payload, str(payload))
        return f"Bearer {payload.get('access_token', '')}"

    health = client.get("/api/health")
    check("health", health.status_code == 200 and health.get_json().get("status") == "ok")

    system_token = login(system_id, admins[system_id]["password"], "admin")
    normal_token = login(normal_id, admins[normal_id]["password"], "admin") if normal_id else None
    student_token = login(student_id, student["password"], "student")

    me = client.get("/api/auth/me", headers={"Authorization": system_token})
    check("auth/me system_admin", me.get_json().get("user", {}).get("role") == "system_admin")

    report = client.get("/api/admin/report", headers={"Authorization": system_token})
    check("system admin report", report.status_code == 200 and report.get_json().get("success"))

    students = client.get("/api/admin/students", headers={"Authorization": system_token})
    students_payload = students.get_json(silent=True) or {}
    check("system admin student list", students.status_code == 200 and students_payload.get("success"))
    leaked = [s for s in students_payload.get("students", []) if "password" in s]
    check("student list hides passwords", not leaked)

    credits = client.get("/api/student/my_credits", headers={"Authorization": student_token})
    credits_payload = credits.get_json(silent=True) or {}
    check("student my_credits", credits.status_code == 200 and credits_payload.get("success"))

    activities = client.get("/api/student/activities", headers={"Authorization": student_token})
    check("student activities", activities.status_code == 200 and activities.get_json().get("success"))

    wrong = client.post(
        "/api/auth/token",
        data={"grant_type": "password", "username": student_id, "password": digest("wrong-password"), "user_type": "student"},
    )
    check("wrong password rejected", wrong.status_code == 401)

    no_token = client.get("/api/admin/report")
    check("missing token rejected", no_token.status_code == 401)

    if normal_token:
        normal_report = client.get("/api/admin/report", headers={"Authorization": normal_token})
        check("normal admin report", normal_report.status_code == 200 and normal_report.get_json().get("success"))
        # Legacy deliberately lets normal admins read the student list.
        normal_students = client.get("/api/admin/students", headers={"Authorization": normal_token})
        normal_payload = normal_students.get_json(silent=True) or {}
        check(
            "normal admin student list hides passwords",
            normal_students.status_code == 200
            and not [s for s in normal_payload.get("students", []) if "password" in s],
        )
        forbidden = client.post("/api/admin/students", json={}, headers={"Authorization": normal_token})
        check("normal admin blocked from student mutation", forbidden.status_code in {401, 403})
        cross = client.get("/api/student/my_credits", headers={"Authorization": normal_token})
        check("admin token blocked from student api", cross.status_code in {401, 403})

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
