"""本机专用的系统维护控制台。

只能通过服务器本机（127.0.0.1 / ::1）访问 http://localhost:5000/local/system，
集中维护三类只允许出现在本机的敏感信息：
- 内置 system 管理员的密码（重置为随机值，仅显示一次）；
- system 的 OTP（二维码与密钥，仅显示一次）；
- 邮件服务配置（SMTP 账号、明文密码、学生邮箱后缀，以及测试发送）。

安全措施：
- 非本机来源一律 404（不暴露页面存在）；
- 页面签发短时表单令牌（HMAC 签名，10 分钟有效），阻止其他网站跨站表单提交；
- system 密码只能随机生成、只在结果页显示一次（避免 CSRF 强设口令）；
- 拒绝跨站浏览器请求（Sec-Fetch-Site 标头存在且非同源时直接拒绝）。
"""

from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import time

from flask import Blueprint, current_app, request

from backend.extensions import db
from backend.models import Admin, EmailConfig
from backend.services import emailer
from backend.services.otp_service import bind_new_totp
from backend.utils.crypto import encrypt_secret
from backend.utils.otp import provisioning_uri, qr_png_data_uri
from backend.utils.passwords import client_password_digest, hash_password_digest


local_admin_bp = Blueprint("local_admin", __name__)

SYSTEM_ADMIN_ID = "system"
FORM_TOKEN_TTL_SECONDS = 600
_LOCAL_ADDRS = {"127.0.0.1", "::1", "localhost"}

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>系统维护（本机专用）</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; background: #f3f3f3; margin: 0;
         display: flex; justify-content: center; padding: 40px 16px; }}
  main {{ background: #fff; border-radius: 12px; padding: 32px; max-width: 560px;
         width: 100%%; box-shadow: 0 8px 32px rgba(0,0,0,.08); }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .warn {{ background: #fff4ce; border-left: 4px solid #ca5010; padding: 10px 14px;
          font-size: 13px; border-radius: 4px; margin-bottom: 20px; }}
  section {{ border-top: 1px solid #e0e0e0; padding-top: 16px; margin-top: 16px; }}
  h2 {{ font-size: 16px; margin: 0 0 6px; }}
  p.desc {{ color: #555; font-size: 13px; margin: 0 0 12px; }}
  label {{ display: block; font-size: 13px; color: #333; margin: 10px 0 4px; }}
  input[type=text], input[type=email], input[type=password] {{
      width: 100%%; box-sizing: border-box; padding: 8px 10px; font-size: 14px;
      border: 1px solid #ccc; border-radius: 6px; }}
  button {{ background: #d13438; color: #fff; border: 0; border-radius: 6px;
          padding: 10px 20px; font-size: 14px; cursor: pointer; margin-top: 12px; }}
  button:hover {{ background: #b52b2f; }}
  button.secondary {{ background: #0078d4; }}
  button.secondary:hover {{ background: #106ebe; }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; }}
  .hint {{ color: #888; font-size: 12px; }}
</style>
</head>
<body>
<main>
  <h1>系统维护</h1>
  <p class="sub">本页面仅允许在服务器本机（localhost）访问。system 密码、OTP 与邮件服务信息只出现在这里。</p>
  <div class="warn">⚠️ 重置类操作立即生效：旧密码/旧验证器立即失效，
  新密码与二维码只在提交后的页面显示一次。</div>
  {content}
</main>
</body>
</html>
"""


def _is_local_request() -> bool:
    if request.remote_addr not in _LOCAL_ADDRS:
        return False
    # 浏览器跨站表单提交会带 Sec-Fetch-Site: cross-site，一律拒绝
    fetch_site = request.headers.get("Sec-Fetch-Site")
    return fetch_site in (None, "same-origin", "same-site", "none")


def _sign(timestamp: int) -> str:
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, str(timestamp).encode("ascii"), hashlib.sha256).hexdigest()


def _issue_form_token() -> str:
    timestamp = int(time.time())
    return f"{timestamp}.{_sign(timestamp)}"


def _valid_form_token(token: str) -> bool:
    try:
        ts_text, signature = token.split(".", 1)
        timestamp = int(ts_text)
    except (ValueError, AttributeError):
        return False
    if abs(time.time() - timestamp) > FORM_TOKEN_TTL_SECONDS:
        return False
    return hmac.compare_digest(signature, _sign(timestamp))


def _render(content: str, status: int = 200):
    return _PAGE.format(content=content), status, {"Content-Type": "text/html; charset=utf-8"}


def _check_request():
    """Returns an error response, or None when the request may proceed."""
    if not _is_local_request():
        return _render("<p>页面不存在。</p>", 404)
    if request.method == "POST" and not _valid_form_token(request.form.get("form_token", "")):
        return _render("<p>表单已过期，请返回 <a href='/local/system'>维护页面</a> 重新操作。</p>", 403)
    return None


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _email_config_section(token: str) -> str:
    config, password = emailer.get_email_config()
    service_email = _esc(config.service_email) if config else ""
    suffix = _esc(config.student_email_suffix) if config else ""
    saved_password = _esc(password)
    password_block = (
        f"""
        <label>当前已保存的密码/授权码</label>
        <input type="text" value="{saved_password}" readonly
               style="background:#f5f5f5;font-family:monospace">
        """
        if password
        else '<p class="hint">尚未保存密码/授权码。</p>'
    )
    return f"""
  <section>
    <h2>邮件服务配置</h2>
    <p class="desc">用于发送注册验证码、OTP 二维码和密码重置邮件。
    QQ/163 邮箱需使用 SMTP 授权码；Outlook 个人邮箱已禁用 SMTP。</p>
    <form method="post" action="/local/system/email-config">
      <input type="hidden" name="form_token" value="{token}">
      <label>服务邮箱</label>
      <input type="email" name="service_email" value="{service_email}">
      {password_block}
      <label>新密码/授权码（留空保持不变）</label>
      <input type="password" name="service_email_password" value="">
      <label>学生邮箱后缀</label>
      <input type="text" name="student_email_suffix" value="{suffix}" placeholder="@example.edu.cn">
      <button type="submit">保存邮箱配置</button>
    </form>
    <form method="post" action="/local/system/test-email">
      <input type="hidden" name="form_token" value="{token}">
      <label>发送测试邮件到</label>
      <input type="email" name="test_email" placeholder="接收测试邮件的地址">
      <button type="submit" class="secondary">发送测试邮件</button>
    </form>
  </section>
"""


def _console_content() -> str:
    token = _issue_form_token()
    actions = f"""
  <section>
    <h2>重置 system 密码</h2>
    <p class="desc">生成新的随机强密码，仅在结果页显示一次。</p>
    <form method="post" action="/local/system/reset-password">
      <input type="hidden" name="form_token" value="{token}">
      <button type="submit">重置密码</button>
    </form>
  </section>
  <section>
    <h2>重置 system 动态验证码（OTP）</h2>
    <p class="desc">生成新的 OTP 密钥并显示绑定二维码；旧验证器立即失效。</p>
    <form method="post" action="/local/system/reset-otp">
      <input type="hidden" name="form_token" value="{token}">
      <button type="submit">重置 OTP</button>
    </form>
  </section>
"""
    return actions + _email_config_section(token)


@local_admin_bp.get("/local/system")
def console():
    error = _check_request()
    if error:
        return error
    return _render(_console_content())


@local_admin_bp.post("/local/system/reset-password")
def reset_password():
    error = _check_request()
    if error:
        return error
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        return _render("<p>system 账号不存在，请重启服务以自动创建。</p>", 500)
    password = secrets.token_urlsafe(12)
    admin.password_hash = hash_password_digest(client_password_digest(password))
    db.session.commit()
    return _render(
        f"""
        <section>
          <h2>密码已重置</h2>
          <p class="desc">新密码（仅显示这一次，请立即保存）：</p>
          <p><code style="font-size:18px">{password}</code></p>
          <p class="desc">登录时还需要动态验证码；如未绑定或已失效，请返回上一页重置 OTP。</p>
          <p><a href="/local/system">返回维护页面</a></p>
        </section>
        """
    )


@local_admin_bp.post("/local/system/reset-otp")
def reset_otp():
    error = _check_request()
    if error:
        return error
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        return _render("<p>system 账号不存在，请重启服务以自动创建。</p>", 500)
    secret, _uri = bind_new_totp(admin)
    db.session.commit()
    qr = qr_png_data_uri(provisioning_uri(secret, SYSTEM_ADMIN_ID))
    return _render(
        f"""
        <section>
          <h2>OTP 已重置</h2>
          <p class="desc">请立即用验证器应用（Microsoft Authenticator / Google Authenticator /
          微信或腾讯系验证器小程序等）扫码绑定，或手动输入密钥：</p>
          <p style="text-align:center"><img src="{qr}" alt="OTP 二维码" width="220" height="220"></p>
          <p><code style="font-size:15px;word-break:break-all">{secret}</code></p>
          <p class="desc">此页面关闭后二维码与密钥无法再次查看。</p>
          <p><a href="/local/system">返回维护页面</a></p>
        </section>
        """
    )


@local_admin_bp.post("/local/system/email-config")
def save_email_config():
    error = _check_request()
    if error:
        return error
    config = db.session.get(EmailConfig, 1)
    if config is None:
        config = EmailConfig(id=1)
        db.session.add(config)

    config.service_email = request.form.get("service_email", "").strip()
    config.student_email_suffix = request.form.get("student_email_suffix", "").strip()
    new_password = request.form.get("service_email_password", "")
    if new_password:
        config.service_email_password_encrypted = encrypt_secret(
            new_password, current_app.config["SECRET_KEY"]
        )
    db.session.commit()
    return _render(
        """
        <section>
          <h2>邮箱配置已保存</h2>
          <p><a href="/local/system">返回维护页面</a></p>
        </section>
        """
    )


@local_admin_bp.post("/local/system/test-email")
def test_email():
    error = _check_request()
    if error:
        return error
    address = request.form.get("test_email", "").strip()
    if not address:
        return _render(
            """
            <section>
              <h2>测试邮件</h2>
              <p class="desc">请输入接收测试邮件的地址。</p>
              <p><a href="/local/system">返回维护页面</a></p>
            </section>
            """
        )
    success, message, debug_info = emailer.send_test_email(address, debug=True)
    debug_block = ""
    if debug_info:
        lines = "<br>".join(_esc(line) for line in debug_info)
        debug_block = f'<p class="hint" style="font-family:monospace">{lines}</p>'
    status_text = "发送成功 ✓" if success else f"发送失败：{_esc(message)}"
    return _render(
        f"""
        <section>
          <h2>测试邮件：{status_text}</h2>
          {debug_block}
          <p><a href="/local/system">返回维护页面</a></p>
        </section>
        """
    )
