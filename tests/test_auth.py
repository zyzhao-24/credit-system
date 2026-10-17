"""Authentication API tests (password + mandatory TOTP two-step)."""

import pyotp

from backend.models import Admin, Student
from backend.services.otp_service import get_totp_secret
from backend.utils.passwords import client_password_digest
from mailstub import SENT_MAIL


def _step1(client, username, password, user_type):
    return client.post(
        "/api/auth/token",
        data={
            "grant_type": "password",
            "username": username,
            "password": client_password_digest(password),
            "user_type": user_type,
        },
    )


def test_password_step_requires_otp_then_me(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()

    step1 = _step1(client, "1001", "pass123", "student")
    assert step1.status_code == 200
    payload = step1.get_json()
    # 密码正确不再直接发访问令牌，而是进入 OTP 步骤
    assert payload["otp_required"] is True
    assert "access_token" not in payload
    assert payload["otp_ticket"]

    # 首次登录的学生未绑定 OTP：系统自动生成并（在测试中以打桩方式）发送绑定邮件
    student = database.session.get(Student, "1001")
    secret = get_totp_secret(student)
    assert secret
    assert any(mail["to"].startswith("1001") for mail in SENT_MAIL)
    assert any(mail["attachments"] for mail in SENT_MAIL)

    wrong = client.post(
        "/api/auth/token/verify",
        json={"otp_ticket": payload["otp_ticket"], "otp_code": "000000"},
    )
    assert wrong.get_json()["success"] is False

    step2 = client.post(
        "/api/auth/token/verify",
        json={"otp_ticket": payload["otp_ticket"], "otp_code": pyotp.TOTP(secret).now()},
    )
    assert step2.status_code == 200
    tokens = step2.get_json()
    assert tokens["token_type"] == "bearer"
    assert tokens["user_type"] == "student"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["sub"] == "1001"

    assert student.password_hash != "pass123"
    assert student.password_hash.startswith("pbkdf2:sha256:")


def test_admin_two_step_and_legacy_login(app, database, seed_legacy_payload, minimal_payload, login):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()

    # login fixture 内部完成两步验证
    token = login("system", "adminpass", "admin")
    info = client.get("/api/admin/session_info", headers={"Authorization": token})
    assert info.status_code == 200
    assert info.get_json()["role"] == "system_admin"

    # legacy 登录端点同样进入 OTP 步骤而不是直接放行
    # （先通过 login fixture 为普通管理员绑定 OTP）
    login("admin", "adminpass", "admin")
    legacy = client.post(
        "/api/login/admin",
        json={"username": "admin", "password_hash": client_password_digest("adminpass")},
    )
    assert legacy.status_code == 200
    assert legacy.get_json()["otp_required"] is True
    assert "access_token" not in legacy.get_json()


def test_unbound_admin_cannot_self_bind_via_login(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    # system 管理员在 conftest 的建库阶段由 create_app 保证存在，但没有 OTP 密钥
    admin = database.session.get(Admin, "system")
    admin.totp_secret_encrypted = ""
    database.session.commit()

    step1 = _step1(client, "system", "adminpass", "admin")
    assert step1.status_code == 403
    assert "manage.py" in step1.get_json()["message"]


def test_wrong_password_is_rejected(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    response = _step1(app.test_client(), "1001", "wrong-password", "student")
    assert response.status_code == 401


def test_registration_requires_email_code_and_binds_otp(app, database):
    client = app.test_client()

    # 配置学生邮箱后缀（邮件已打桩，不会真实发送）
    from backend.models import EmailConfig

    database.session.add(
        EmailConfig(id=1, service_email="service@example.com", student_email_suffix="@stu.example.com")
    )
    database.session.commit()

    # 未先取验证码直接注册应失败
    direct = client.post(
        "/api/student/register",
        json={
            "name": "新学生",
            "student_id": "2001",
            "phone": "13700000000",
            "wechat": "new-wechat",
            "password": "secret123",
        },
    )
    assert direct.get_json()["success"] is False

    # 发送验证码
    sent = client.post(
        "/api/student/register/send_code",
        json={"student_id": "2001", "name": "新学生"},
    )
    assert sent.status_code == 200
    assert sent.get_json()["success"] is True
    code_mail = next(m for m in SENT_MAIL if m["to"] == "2001@stu.example.com")

    # 从打桩邮件中取出验证码
    import re

    code_match = re.search(r"\b(\d{6})\b", code_mail["body"])
    assert code_match is not None
    code = code_match.group(1)

    response = client.post(
        "/api/student/register",
        json={
            "name": "新学生",
            "student_id": "2001",
            "phone": "13700000000",
            "wechat": "new-wechat",
            "password": "secret123",
            "suggestion": "建议",
            "email_code": code,
        },
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    student = database.session.get(Student, "2001")
    assert student.password_hash.startswith("pbkdf2:sha256:")
    # 报名信息直接落在学生档案上
    assert student.wechat == "new-wechat"
    assert student.phone == "13700000000"
    assert student.info_updated_at is not None
    # 注册成功后 OTP 已绑定，且二维码邮件已（打桩）发送
    assert get_totp_secret(student)
    otp_mail = next(m for m in SENT_MAIL if "绑定动态验证码" in m["subject"])
    assert otp_mail["attachments"]


def test_registration_wrong_email_code_rejected(app, database):
    client = app.test_client()
    from backend.models import EmailConfig

    database.session.add(
        EmailConfig(id=1, service_email="service@example.com", student_email_suffix="@stu.example.com")
    )
    database.session.commit()

    client.post("/api/student/register/send_code", json={"student_id": "2002", "name": "学生乙"})
    response = client.post(
        "/api/student/register",
        json={
            "name": "学生乙",
            "student_id": "2002",
            "phone": "13700000001",
            "wechat": "w",
            "password": "secret123",
            "email_code": "999999",
        },
    )
    assert response.get_json()["success"] is False
    assert database.session.get(Student, "2002") is None
