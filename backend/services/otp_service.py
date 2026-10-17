"""TOTP binding lifecycle for students and admins.

Secrets are stored Fernet-encrypted (same mechanism as the SMTP password).
Binding material is delivered to students via their school email; admins
receive it out-of-band (CLI or the system admin UI) because admin accounts
have no email address.
"""

from __future__ import annotations

from email.mime.image import MIMEImage
from typing import Any

from flask import current_app

from backend.extensions import db
from backend.models import Admin, EmailConfig, Student
from backend.services.emailer import send_email
from backend.utils.crypto import decrypt_secret, encrypt_secret
from backend.utils.otp import (
    generate_totp_secret,
    provisioning_uri,
    qr_png_bytes,
    verify_totp,
)


def get_totp_secret(account: Student | Admin) -> str:
    return decrypt_secret(
        account.totp_secret_encrypted or "", current_app.config["SECRET_KEY"]
    )


def has_totp(account: Student | Admin) -> bool:
    return bool(get_totp_secret(account))


def set_totp_secret(account: Student | Admin, secret: str) -> None:
    account.totp_secret_encrypted = encrypt_secret(
        secret, current_app.config["SECRET_KEY"]
    )


def check_totp(account: Student | Admin, code: str) -> bool:
    secret = get_totp_secret(account)
    return bool(secret) and verify_totp(secret, code)


def bind_new_totp(account: Student | Admin) -> tuple[str, str]:
    """Generate and store a fresh secret; returns (secret, otpauth_uri)."""
    account_id = (
        account.student_id if isinstance(account, Student) else account.admin_id
    )
    secret = generate_totp_secret()
    set_totp_secret(account, secret)
    return secret, provisioning_uri(secret, account_id)


def student_email_address(student_id: str) -> tuple[str | None, str]:
    """Build the school mailbox address for a student from email config."""
    config = db.session.get(EmailConfig, 1)
    if config is None or not config.student_email_suffix:
        return None, "学生邮箱后缀未配置，请联系系统管理员"
    return f"{student_id}{config.student_email_suffix}", ""


def send_totp_binding_email(student: Student, secret: str) -> tuple[bool, str]:
    """Email the OTP QR code to the student's school mailbox.

    Only called from registration and forgot-password flows (and tests stub
    it out) — never from generic test/smoke runs.
    """
    address, error = student_email_address(student.student_id)
    if address is None:
        return False, error
    uri = provisioning_uri(secret, student.student_id)
    qr_png = qr_png_bytes(uri)
    body = f"""
您好，{student.name} 同学：

您正在绑定团校积分系统的动态验证码（OTP）。

请使用支持 TOTP 的验证器应用（如 Microsoft Authenticator、Google
Authenticator、微信“腾讯身份验证器”小程序等）扫描附件中的二维码，
或手动输入密钥：

    {secret}

绑定后，每次登录都需要输入验证器中显示的 6 位动态验证码。

如非本人操作，请立即联系管理员。

---
团校积分系统
"""
    attachments: list[tuple[str, bytes, str]] = [("otp-qrcode.png", qr_png, "image/png")]
    success, message = send_email(
        address, "团校积分系统 - 绑定动态验证码", body, attachments=attachments
    )
    if success:
        return True, f"绑定二维码已发送至 {address}，请查收邮件后输入验证码完成登录"
    return False, message
