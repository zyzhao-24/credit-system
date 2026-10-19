"""Authentication API tests (password + mandatory TOTP two-step)."""

import pyotp

from backend.models import Admin, Student
from backend.services.otp_service import get_totp_secret
from backend.utils.passwords import client_password_digest, verify_password_digest
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
    # OTP 邮件内嵌二维码（Content-ID 图片）并带 HTML 排版
    otp_mail = next(m for m in SENT_MAIL if m["to"].startswith("1001"))
    assert otp_mail["inline_images"]
    assert otp_mail["html"].startswith("<!DOCTYPE html>")

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
    # （先通过 login fixture 为普通管理员绑定 OTP；换一个未信任的 IP 发起，
    #  否则该账号在 127.0.0.1 上处于一周信任期会直接发令牌）
    login("admin", "adminpass", "admin")
    legacy = client.post(
        "/api/login/admin",
        json={"username": "admin", "password_hash": client_password_digest("adminpass")},
        environ_overrides={"REMOTE_ADDR": "203.0.113.9"},
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
    assert "/local/system" in step1.get_json()["message"]


def test_unbound_normal_admin_cannot_login(app, database, seed_legacy_payload, minimal_payload):
    """未绑定 OTP 的普通管理员同样禁止登录，只能由系统管理员中转重置。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    admin = database.session.get(Admin, "admin")
    admin.totp_secret_encrypted = ""
    database.session.commit()

    step1 = _step1(client, "admin", "adminpass", "admin")
    assert step1.status_code == 403
    assert "系统管理员" in step1.get_json()["message"]
    database.session.refresh(admin)
    assert not get_totp_secret(admin)


def test_wrong_password_is_rejected(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    response = _step1(app.test_client(), "1001", "wrong-password", "student")
    assert response.status_code == 401


def test_registration_then_otp_bind_dialog(app, database):
    """注册：邮箱验证码通过才注册；OTP 在注册后弹窗中验证确认才绑定。"""
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
    payload = response.get_json()
    assert payload["success"] is True
    bundle = payload["otp_bind"]
    assert bundle["ticket"] and bundle["otp_secret"] and bundle["otp_qr"].startswith("data:image/png")

    student = database.session.get(Student, "2001")
    assert student.password_hash.startswith("pbkdf2:sha256:")
    # 报名信息直接落在学生档案上
    assert student.wechat == "new-wechat"
    assert student.phone == "13700000000"
    assert student.info_updated_at is not None
    # 注册本身不绑定 OTP、也不发 OTP 邮件（绑定在弹窗中验证确认才生效）
    assert not get_totp_secret(student)
    assert not any("动态验证码" in m["subject"] for m in SENT_MAIL)

    # 错误验证码不生效
    wrong = client.post(
        "/api/auth/otp/bind/confirm", json={"ticket": bundle["ticket"], "otp_code": "000000"}
    )
    assert wrong.get_json()["success"] is False
    database.session.refresh(student)
    assert not get_totp_secret(student)

    # 正确验证码确认后才绑定
    ok = client.post(
        "/api/auth/otp/bind/confirm",
        json={"ticket": bundle["ticket"], "otp_code": pyotp.TOTP(bundle["otp_secret"]).now()},
    )
    assert ok.get_json()["success"] is True
    database.session.refresh(student)
    assert get_totp_secret(student) == bundle["otp_secret"]


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


def test_forgot_password_email_code_then_optional_otp_rebind(
    app, database, seed_legacy_payload, minimal_payload
):
    """忘记密码与注册同构：邮箱验证码 → 重置密码 → 可选弹窗重绑 OTP（验证才生效）。"""
    import re

    from backend.models import EmailConfig

    seed_legacy_payload(minimal_payload)
    config = database.session.get(EmailConfig, 1)
    config.service_email = "service@example.com"
    config.student_email_suffix = "@stu.example.com"
    database.session.commit()
    client = app.test_client()
    student = database.session.get(Student, "1001")
    old_password_hash = student.password_hash
    old_otp = get_totp_secret(student)

    # 未知学号返回通用提示（不枚举学号），已存在学号发送验证码
    ghost = client.post("/api/student/forgot_password/send_code", json={"student_id": "9999"})
    assert ghost.get_json()["success"] is True
    sent = client.post("/api/student/forgot_password/send_code", json={"student_id": "1001"})
    assert sent.get_json()["success"] is True
    code_mail = next(m for m in SENT_MAIL if "重置密码验证码" in m["subject"])
    code = re.search(r"\b(\d{6})\b", code_mail["body"]).group(1)

    # 验证码错误：密码不变
    wrong = client.post(
        "/api/student/forgot_password",
        json={"student_id": "1001", "new_password": "brandnew1", "email_code": "000000"},
    )
    assert wrong.get_json()["success"] is False
    database.session.refresh(student)
    assert student.password_hash == old_password_hash

    # 验证码正确：密码重置，并返回可选的 OTP 重绑票据
    ok = client.post(
        "/api/student/forgot_password",
        json={"student_id": "1001", "new_password": "brandnew1", "email_code": code},
    )
    payload = ok.get_json()
    assert payload["success"] is True
    bundle = payload["otp_bind"]
    database.session.refresh(student)
    assert verify_password_digest(student.password_hash, client_password_digest("brandnew1"))
    # 重绑验证前 OTP 保持原样；验证通过才替换
    assert get_totp_secret(student) == old_otp
    confirm = client.post(
        "/api/auth/otp/bind/confirm",
        json={"ticket": bundle["ticket"], "otp_code": pyotp.TOTP(bundle["otp_secret"]).now()},
    )
    assert confirm.get_json()["success"] is True
    database.session.refresh(student)
    assert get_totp_secret(student) == bundle["otp_secret"]

    # 新密码 + 新 OTP 可以完成两步登录
    step1 = _step1(client, "1001", "brandnew1", "student")
    assert step1.status_code == 200
    step2 = client.post(
        "/api/auth/token/verify",
        json={
            "otp_ticket": step1.get_json()["otp_ticket"],
            "otp_code": pyotp.TOTP(bundle["otp_secret"]).now(),
        },
    )
    assert step2.status_code == 200


def test_student_self_otp_reset_requires_code(app, database, seed_legacy_payload, minimal_payload, login):
    """学生主动重置 OTP：候选二维码验证通过才生效，否则旧 OTP 不变。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    token = login("1001", "pass123", "student")
    headers = {"Authorization": token}
    student = database.session.get(Student, "1001")
    old_otp = get_totp_secret(student)
    assert old_otp

    begin = client.post("/api/student/otp/reset", headers=headers)
    bundle = begin.get_json()["otp_bind"]
    assert bundle["ticket"] and bundle["otp_qr"].startswith("data:image/png")
    database.session.refresh(student)
    assert get_totp_secret(student) == old_otp  # 尚未生效

    wrong = client.post(
        "/api/auth/otp/bind/confirm", json={"ticket": bundle["ticket"], "otp_code": "000000"}
    )
    assert wrong.get_json()["success"] is False
    database.session.refresh(student)
    assert get_totp_secret(student) == old_otp

    ok = client.post(
        "/api/auth/otp/bind/confirm",
        json={"ticket": bundle["ticket"], "otp_code": pyotp.TOTP(bundle["otp_secret"]).now()},
    )
    assert ok.get_json()["success"] is True
    database.session.refresh(student)
    assert get_totp_secret(student) == bundle["otp_secret"] != old_otp


def test_trusted_device_skips_otp_for_a_week(app, database, seed_legacy_payload, minimal_payload):
    """OTP 验证成功后，一周内同设备（Cookie）或同 IP 登录第一步直接发令牌。"""
    seed_legacy_payload(minimal_payload)
    from datetime import datetime, timedelta

    from backend.models import TrustedDevice

    client = app.test_client()
    # 首次登录：仍需 OTP（学生未绑定时自动发绑定邮件）
    step1 = _step1(client, "1001", "pass123", "student")
    assert step1.get_json()["otp_required"] is True
    student = database.session.get(Student, "1001")
    secret = get_totp_secret(student)
    step2 = client.post(
        "/api/auth/token/verify",
        json={"otp_ticket": step1.get_json()["otp_ticket"], "otp_code": pyotp.TOTP(secret).now()},
    )
    assert step2.get_json()["success"] is True
    # 验证成功后写入信任记录并下发设备 Cookie
    assert "trusted_device" in step2.headers.get("Set-Cookie", "")
    rows = TrustedDevice.query.filter_by(user_type="student", account_id="1001").all()
    assert len(rows) == 1
    assert rows[0].expires_at > datetime.now() + timedelta(days=6)

    # 同设备（带 Cookie）：第一步直接发令牌
    again = _step1(client, "1001", "pass123", "student")
    assert again.status_code == 200
    assert again.get_json().get("access_token")
    assert not again.get_json().get("otp_required")

    # 无 Cookie 但同 IP（换浏览器、网络未变）：同样免 OTP
    other_browser = app.test_client()
    by_ip = other_browser.post(
        "/api/auth/token",
        data={
            "grant_type": "password",
            "username": "1001",
            "password": client_password_digest("pass123"),
            "user_type": "student",
        },
    )
    assert by_ip.get_json().get("access_token")

    # 信任是账号级的：同 IP 的别的账号仍要 OTP
    other_account = other_browser.post(
        "/api/auth/token",
        data={
            "grant_type": "password",
            "username": "1002",
            "password": client_password_digest("pass456"),
            "user_type": "student",
        },
    )
    assert other_account.get_json()["otp_required"] is True

    # 信任过期后恢复 OTP 两步（惰性清理会把过期行删掉）
    rows[0].expires_at = datetime.now() - timedelta(seconds=1)
    database.session.commit()
    expired = _step1(client, "1001", "pass123", "student")
    assert expired.get_json()["otp_required"] is True
    assert TrustedDevice.query.filter_by(user_type="student", account_id="1001").count() == 0


def test_otp_reset_revokes_trusted_login(
    app, database, seed_legacy_payload, minimal_payload, login
):
    """OTP 被重置后，信任期内的 IP/设备也必须重新过 OTP（修复静默绕过漏洞）。"""
    seed_legacy_payload(minimal_payload)
    from backend.models import TrustedDevice

    client = app.test_client()
    # 学生完成一次 OTP 验证，进入信任期
    step1 = _step1(client, "1001", "pass123", "student")
    student = database.session.get(Student, "1001")
    secret = get_totp_secret(student)
    step2 = client.post(
        "/api/auth/token/verify",
        json={"otp_ticket": step1.get_json()["otp_ticket"], "otp_code": pyotp.TOTP(secret).now()},
    )
    assert step2.get_json()["success"] is True
    assert TrustedDevice.query.filter_by(user_type="student", account_id="1001").count() == 1
    # 信任期内同 IP 免 OTP
    assert _step1(client, "1001", "pass123", "student").get_json().get("access_token")

    # 系统管理员将该学生 OTP 置为未绑定 → 信任记录立即作废
    system = login("system", "adminpass", "admin")
    reset = client.post(
        "/api/admin/students/reset_otp",
        json={"student_id": "1001"},
        headers={"Authorization": system},
    )
    assert reset.get_json()["success"] is True
    assert TrustedDevice.query.filter_by(user_type="student", account_id="1001").count() == 0

    # 同 IP 再登录：必须重新过 OTP（未绑定则自动经邮箱重绑，邮件已打桩）
    after = _step1(client, "1001", "pass123", "student")
    assert after.get_json()["otp_required"] is True
    assert not after.get_json().get("access_token")
