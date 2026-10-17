"""TOTP binding lifecycle for students and admins.

Secrets are stored Fernet-encrypted (same mechanism as the SMTP password).
Binding material is delivered to students via their school email; admins
receive it out-of-band (the system admin UI or the localhost console).

Binding is a two-phase flow wherever a human must prove possession of the
new secret: `begin_pending_otp` issues a signed ticket carrying the
Fernet-encrypted *candidate* secret, and only `confirm_pending_otp` (which
requires a valid 6-digit code from that candidate) writes it to the account.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from backend.auth.jwt import decode_token, issue_token
from backend.extensions import db
from backend.models import Admin, EmailConfig, Student
from backend.services import mail_templates
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


def clear_totp(account: Student | Admin) -> None:
    """Mark OTP as unbound; the next login/reset flow re-provisions it."""
    account.totp_secret_encrypted = ""


def check_totp(account: Student | Admin, code: str) -> bool:
    secret = get_totp_secret(account)
    return bool(secret) and verify_totp(secret, code)


def bind_new_totp(account: Student | Admin) -> tuple[str, str]:
    """Generate and store a fresh secret immediately; returns (secret, uri).

    Used where immediate effect is intended: first login of a student whose
    OTP was reset (the code is delivered by email) and test/CLI provisioning.
    """
    account_id = (
        account.student_id if isinstance(account, Student) else account.admin_id
    )
    secret = generate_totp_secret()
    set_totp_secret(account, secret)
    return secret, provisioning_uri(secret, account_id)


# ========== 待生效绑定票据（验证通过才写入） ==========

PENDING_OTP_TICKET_SECONDS = 600
PENDING_OTP_PURPOSES = {
    "register_bind",      # 注册成功后弹窗绑定
    "student_reset",      # 学生主动重置 / 忘记密码成功后重新绑定
    "admin_reset",        # 系统管理员重置管理员 OTP（二次确认生效）
    "local_system_reset", # 本机维护页重置 system OTP
}


def _account_id_of(account: Student | Admin) -> str:
    return account.student_id if isinstance(account, Student) else account.admin_id


def begin_pending_otp(
    account: Student | Admin,
    user_type: str,
    purpose: str,
) -> tuple[str, str]:
    """Create a candidate secret and a signed ticket; nothing is written yet.

    Returns (ticket, candidate_secret). The ticket carries the candidate
    Fernet-encrypted, so cancelling the flow leaves the account untouched.
    """
    assert purpose in PENDING_OTP_PURPOSES, purpose
    key = current_app.config["SECRET_KEY"]
    candidate = generate_totp_secret()
    extra: dict[str, Any] = {
        "purpose": purpose,
        "enc_secret": encrypt_secret(candidate, key),
    }
    ticket = issue_token(
        {"id": _account_id_of(account), "user_type": user_type, "role": "otp_bind_pending"},
        key,
        PENDING_OTP_TICKET_SECONDS,
        extra=extra,
    )
    return ticket, candidate


def decode_pending_otp(ticket: str) -> tuple[dict[str, Any] | None, str]:
    """Validate a pending-bind ticket; returns (claims, error_message)."""
    try:
        claims = decode_token(ticket, current_app.config["SECRET_KEY"])
    except Exception:
        return None, "绑定请求已过期，请重新操作"
    if claims.get("role") != "otp_bind_pending" or claims.get("purpose") not in PENDING_OTP_PURPOSES:
        return None, "无效的绑定请求"
    secret = decrypt_secret(claims.get("enc_secret", ""), current_app.config["SECRET_KEY"])
    if not secret:
        return None, "无效的绑定请求"
    claims["candidate_secret"] = secret
    return claims, ""


def confirm_pending_otp(account: Student | Admin, claims: dict[str, Any], code: str) -> bool:
    """Write the candidate secret only when the code proves possession."""
    return verify_totp(claims["candidate_secret"], code)


def pending_otp_bundle(ticket: str, candidate: str, account_id: str) -> dict[str, str]:
    """Response payload for clients to render the QR binding dialog."""
    uri = provisioning_uri(candidate, account_id)
    from backend.utils.otp import qr_png_data_uri

    return {
        "ticket": ticket,
        "otp_secret": candidate,
        "otp_uri": uri,
        "otp_qr": qr_png_data_uri(uri),
    }


# ========== 邮件 ==========

OTP_QR_CID = "otp-qrcode"


def student_email_address(student_id: str) -> tuple[str | None, str]:
    """Build the school mailbox address for a student from email config."""
    config = db.session.get(EmailConfig, 1)
    if config is None or not config.student_email_suffix:
        return None, "学生邮箱后缀未配置，请联系系统管理员"
    return f"{student_id}{config.student_email_suffix}", ""


def _otp_mail_bodies(name: str, secret: str, intro: str) -> tuple[str, str]:
    """Plain + HTML bodies for an OTP binding/reset email."""
    plain = f"""
您好，{name} 同学：

{intro}

请使用支持 TOTP 的验证器应用（如 Microsoft Authenticator、Google
Authenticator、微信"腾讯身份验证器"小程序等）扫描邮件中的二维码，
或手动输入密钥：

    {secret}

绑定后，每次登录都需要输入验证器中显示的 6 位动态验证码。

如非本人操作，请立即联系管理员。

---
团校积分系统
"""
    html = mail_templates.render_mail_html(
        "动态验证码（OTP）",
        mail_templates.greeting(name)
        + mail_templates.paragraph(intro)
        + mail_templates.paragraph(
            "请使用支持 TOTP 的验证器应用（Microsoft / Google Authenticator、"
            "微信“腾讯身份验证器”小程序等）扫描下方二维码，或手动输入密钥完成绑定："
        )
        + mail_templates.qr_image(OTP_QR_CID)
        + mail_templates.secret_block(secret)
        + mail_templates.hint("绑定后，每次登录都需要输入验证器中显示的 6 位动态验证码。"),
    )
    return plain, html


def _send_otp_mail(student: Student, secret: str, intro: str) -> tuple[bool, str]:
    address, error = student_email_address(student.student_id)
    if address is None:
        return False, error
    uri = provisioning_uri(secret, student.student_id)
    qr_png = qr_png_bytes(uri)
    plain, html = _otp_mail_bodies(student.name, secret, intro)
    success, message = send_email(
        address,
        "团校积分系统 - 动态验证码（OTP）",
        plain,
        html=html,
        inline_images=[(OTP_QR_CID, qr_png, "image/png")],
    )
    return success, message


def send_totp_binding_email(student: Student, secret: str) -> tuple[bool, str]:
    """Email the OTP QR code to the student's school mailbox.

    Only called from the login auto-provision flow (and tests stub it out) —
    never from generic test/smoke runs.
    """
    success, message = _send_otp_mail(
        student, secret, "您正在绑定团校积分系统的动态验证码（OTP）。"
    )
    if success:
        return True, f"绑定二维码已发送至 {address_hint(student)}，请查收邮件后输入验证码完成登录"
    return False, message


def address_hint(student: Student) -> str:
    address, _error = student_email_address(student.student_id)
    return address or "您的学号邮箱"
