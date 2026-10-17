"""SMTP email service with legacy server inference behavior."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import Any

from flask import current_app

from backend.extensions import db
from backend.models import EmailConfig
from backend.utils.crypto import decrypt_secret


def smtp_profile(service_email: str) -> dict[str, Any]:
    if "qq.com" in service_email:
        return {"server": "smtp.qq.com", "port": 587, "ssl": False, "type": "QQ邮箱"}
    if "163.com" in service_email:
        return {"server": "smtp.163.com", "port": 465, "ssl": True, "type": "163邮箱"}
    if "126.com" in service_email:
        return {"server": "smtp.126.com", "port": 465, "ssl": True, "type": "126邮箱"}
    if "gmail.com" in service_email:
        return {"server": "smtp.gmail.com", "port": 587, "ssl": False, "type": "Gmail"}
    if any(domain in service_email for domain in ("outlook.com", "hotmail.com", "live.com")):
        return {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False, "type": "Outlook"}
    domain = service_email.split("@")[-1]
    return {"server": f"smtp.{domain}", "port": 587, "ssl": False, "type": "自动检测"}


def get_email_config() -> tuple[EmailConfig | None, str]:
    config = db.session.get(EmailConfig, 1)
    if config is None:
        return None, ""
    password = decrypt_secret(
        config.service_email_password_encrypted,
        current_app.config["SECRET_KEY"],
    )
    return config, password


def send_email(
    to_email: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> tuple[bool, str]:
    config, password = get_email_config()
    if config is None or not config.service_email or not password:
        return False, "邮箱配置不完整，请在服务器本机访问 /local/system 配置服务邮箱"

    profile = smtp_profile(config.service_email)
    try:
        message = MIMEMultipart()
        message["From"] = config.service_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))
        for filename, content, mime_type in attachments or []:
            maintype, subtype = mime_type.split("/", 1)
            part = MIMEBase(maintype, subtype)
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(part)

        if profile["ssl"]:
            server = smtplib.SMTP_SSL(profile["server"], profile["port"], timeout=15)
        else:
            server = smtplib.SMTP(profile["server"], profile["port"], timeout=15)
            server.starttls()
        server.login(config.service_email, password)
        server.send_message(message)
        server.quit()
        return True, "邮件发送成功"
    except smtplib.SMTPAuthenticationError as exc:
        if "qq.com" in config.service_email:
            return False, "认证失败：请确认使用QQ邮箱授权码（不是QQ密码）"
        if "163.com" in config.service_email or "126.com" in config.service_email:
            return False, "认证失败：请确认已开启SMTP服务并使用授权密码"
        if "gmail.com" in config.service_email:
            return False, "认证失败：请确认使用应用专用密码并已开启两步验证"
        return False, f"认证失败：{exc}"
    except smtplib.SMTPConnectError:
        return False, "连接失败：无法连接到邮件服务器，请检查网络连接"
    except Exception as exc:
        return False, f"发送失败：{exc}"


def send_test_email(to_email: str, debug: bool = False) -> tuple[bool, str, list[str] | None]:
    debug_info: list[str] = []
    config, password = get_email_config()
    if config is None or not config.service_email or not password:
        return False, "请先配置服务邮箱", debug_info if debug else None

    profile = smtp_profile(config.service_email)
    if debug:
        debug_info.extend(
            [
                f"服务邮箱: {config.service_email}",
                f"密码长度: {len(password)} 字符",
                f"邮箱类型: {profile['type']}",
                f"SMTP服务器: {profile['server']}",
                f"端口: {profile['port']}",
                f"连接方式: {'SSL' if profile['ssl'] else 'TLS'}",
            ]
        )

    body = """这是一封测试邮件。

如果您收到这封邮件，说明邮箱配置成功！

---
团校积分系统"""
    success, message = send_email(to_email, "团校积分系统 - 邮箱配置测试", body)
    if debug:
        debug_info.append("✓ 邮件发送成功！" if success else f"✗ {message}")
    return success, message if success else message, debug_info if debug else None
