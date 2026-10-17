"""Read-only dual-role JWT smoke test against a migrated database.

Uses credentials from data.json to exercise the real two-step login path
(password + TOTP), then checks representative endpoints for each role.
OTP secrets are provisioned directly in the database (equivalent to
`manage.py set-otp`), so no email is ever sent. It performs no mutations
beyond OTP binding and the idempotent login-time questionnaire backfill.
Run from the project root:

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

    # 预绑定 OTP（等价于 manage.py set-otp，直接写库、不发送邮件），
    # 否则学生首次登录会自动绑定并触发真实的 SMTP 发送。
    import pyotp

    from backend.extensions import db
    from backend.models import Admin, Student
    from backend.services.otp_service import bind_new_totp, get_totp_secret, has_totp

    accounts = [("admin", system_id), ("student", student_id)]
    if normal_id:
        accounts.append(("admin", normal_id))
    with app.app_context():
        for user_type, account_id in accounts:
            model = Student if user_type == "student" else Admin
            account = db.session.get(model, account_id)
            if account is not None and not has_totp(account):
                bind_new_totp(account)
        db.session.commit()

    def login(username: str, password: str, user_type: str) -> str:
        step1 = client.post(
            "/api/auth/token",
            data={
                "grant_type": "password",
                "username": username,
                "password": digest(password),
                "user_type": user_type,
            },
        )
        payload = step1.get_json(silent=True) or {}
        if not (step1.status_code == 200 and payload.get("otp_required") and payload.get("otp_ticket")):
            check(f"token login {user_type}:{username} (password step)", False, str(payload))
            return ""
        with app.app_context():
            model = Student if user_type == "student" else Admin
            account = db.session.get(model, username)
            secret = get_totp_secret(account) if account is not None else ""
        if not secret:
            check(f"token login {user_type}:{username}", False, "账号不存在或未绑定 OTP")
            return ""
        step2 = client.post(
            "/api/auth/token/verify",
            json={"otp_ticket": payload["otp_ticket"], "otp_code": pyotp.TOTP(secret).now()},
        )
        final = step2.get_json(silent=True) or {}
        check(
            f"token login {user_type}:{username}",
            step2.status_code == 200 and "access_token" in final,
            str(final),
        )
        return f"Bearer {final.get('access_token', '')}"

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
