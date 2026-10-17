"""Localhost-only system account console tests."""

import re

from backend.models import Admin, EmailConfig
from backend.services.otp_service import has_totp
from backend.utils.passwords import client_password_digest, verify_password_digest
from mailstub import SENT_MAIL

TOKEN_PATTERN = re.compile(r'form_token" value="([^"]+)"')


def _form_token(client) -> str:
    page = client.get("/local/system")
    assert page.status_code == 200
    match = TOKEN_PATTERN.search(page.get_data(as_text=True))
    assert match is not None
    return match.group(1)


def test_console_hidden_from_remote_clients(app, database):
    remote = {"REMOTE_ADDR": "8.8.8.8"}
    assert app.test_client().get("/local/system", environ_overrides=remote).status_code == 404
    assert (
        app.test_client().post("/local/system/reset-password", environ_overrides=remote).status_code
        == 404
    )


def test_console_requires_signed_form_token(app, database):
    client = app.test_client()
    forged = client.post("/local/system/reset-password", data={"form_token": "bogus"})
    assert forged.status_code == 403
    missing = client.post("/local/system/reset-otp")
    assert missing.status_code == 403


def test_console_reset_password_and_otp(app, database):
    import pyotp

    client = app.test_client()
    # create_app 保证 system 账号存在
    admin = database.session.get(Admin, "system")
    assert admin is not None

    token = _form_token(client)
    reset = client.post("/local/system/reset-password", data={"form_token": token})
    assert reset.status_code == 200
    match = re.search(r'<span class="secret">([^<]+)</span>', reset.get_data(as_text=True))
    assert match is not None
    new_password = match.group(1)
    database.session.refresh(admin)
    assert verify_password_digest(admin.password_hash, client_password_digest(new_password))

    # OTP 第一步：生成候选二维码但不生效
    token = _form_token(client)
    otp = client.post("/local/system/reset-otp", data={"form_token": token})
    assert otp.status_code == 200
    page = otp.get_data(as_text=True)
    assert "data:image/png;base64," in page
    database.session.refresh(admin)
    assert not has_totp(admin)  # 确认前保持未绑定

    ticket = re.search(r'bind_ticket" value="([^"]+)"', page).group(1)
    candidate = re.search(r'<span class="secret">([^<]+)</span>', page).group(1)
    confirm_token = TOKEN_PATTERN.search(page).group(1)

    # 错误验证码不生效
    bad = client.post(
        "/local/system/reset-otp/confirm",
        data={"form_token": confirm_token, "bind_ticket": ticket, "otp_code": "000000"},
    )
    assert bad.status_code == 400
    database.session.refresh(admin)
    assert not has_totp(admin)

    # 正确验证码确认后才生效
    ok = client.post(
        "/local/system/reset-otp/confirm",
        data={
            "form_token": confirm_token,
            "bind_ticket": ticket,
            "otp_code": pyotp.TOTP(candidate).now(),
        },
    )
    assert ok.status_code == 200
    database.session.refresh(admin)
    assert has_totp(admin)


def test_console_reset_password_accepts_custom_value(app, database):
    client = app.test_client()
    admin = database.session.get(Admin, "system")

    # 自定义密码生效
    token = _form_token(client)
    custom = client.post(
        "/local/system/reset-password",
        data={"form_token": token, "new_password": "MyOwnPassw0rd!"},
    )
    assert custom.status_code == 200
    assert "MyOwnPassw0rd!" in custom.get_data(as_text=True)
    database.session.refresh(admin)
    assert verify_password_digest(admin.password_hash, client_password_digest("MyOwnPassw0rd!"))

    # 太短的自定义密码被拒绝
    token = _form_token(client)
    short = client.post(
        "/local/system/reset-password",
        data={"form_token": token, "new_password": "abc"},
    )
    assert short.status_code == 400
    database.session.refresh(admin)
    assert verify_password_digest(admin.password_hash, client_password_digest("MyOwnPassw0rd!"))


def test_console_email_config_only_available_here(app, database):
    client = app.test_client()

    # 邮件配置 API 已不存在：信息只能出现在本机维护页
    # （POST 命中 SPA 兜底路由的方法限制返回 405，也算端点已移除）
    assert client.get("/api/admin/email_config").status_code == 404
    assert client.post("/api/admin/test_email", json={}).status_code in {404, 405}

    token = _form_token(client)
    saved = client.post(
        "/local/system/email-config",
        data={
            "form_token": token,
            "service_email": "service@example.com",
            "service_email_password": "smtp-secret",
            "student_email_suffix": "@stu.example.com",
        },
    )
    assert saved.status_code == 200

    config = database.session.get(EmailConfig, 1)
    assert config.service_email == "service@example.com"
    assert config.student_email_suffix == "@stu.example.com"

    # 页面上能看到明文密码（仅此页面）
    page = client.get("/local/system").get_data(as_text=True)
    assert "service@example.com" in page
    assert "smtp-secret" in page

    # 测试邮件走打桩通道，不真实发送
    token = _form_token(client)
    sent = client.post(
        "/local/system/test-email",
        data={"form_token": token, "test_email": "someone@example.com"},
    )
    assert sent.status_code == 200
    assert "发送成功" in sent.get_data(as_text=True)
    assert any(mail["to"] == "someone@example.com" for mail in SENT_MAIL)

    # 留空密码保持不变
    token = _form_token(client)
    client.post(
        "/local/system/email-config",
        data={
            "form_token": token,
            "service_email": "service@example.com",
            "service_email_password": "",
            "student_email_suffix": "@stu.example.com",
        },
    )
    page = client.get("/local/system").get_data(as_text=True)
    assert "smtp-secret" in page
