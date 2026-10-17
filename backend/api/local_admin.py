"""本机专用的系统维护控制台。

只能通过服务器本机（127.0.0.1 / ::1）访问 http://localhost:5000/local/system，
集中维护三类只允许出现在本机的敏感信息：
- 内置 system 管理员的密码（可自定义，留空则随机生成）；
- system 的 OTP（二维码与密钥，仅显示一次）；
- 邮件服务配置（SMTP 账号、明文密码、学生邮箱后缀，以及测试发送）。

安全措施：
- 非本机来源一律 404（不暴露页面存在）；
- 页面签发短时表单令牌（HMAC 签名，10 分钟有效），阻止其他网站跨站表单提交
  （令牌不可被跨站读取，因此自定义密码也无法被 CSRF 预设）；
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
MIN_PASSWORD_LENGTH = 8
_LOCAL_ADDRS = {"127.0.0.1", "::1", "localhost"}

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>系统维护 · 本机专用</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 0;
         background: linear-gradient(180deg, #eef1f5 0%%, #f7f7f8 100%%);
         min-height: 100vh; color: #1b1b1b; }}
  .topbar {{ background: #1b1b1b; color: #fff; padding: 18px 24px;
            display: flex; align-items: center; gap: 12px; }}
  .topbar .dot {{ width: 10px; height: 10px; border-radius: 50%%;
                 background: #4cc2ff; box-shadow: 0 0 8px #4cc2ff; }}
  .topbar h1 {{ font-size: 17px; margin: 0; font-weight: 600; letter-spacing: .5px; }}
  .topbar .badge {{ margin-left: auto; font-size: 12px; color: #9fd8ff;
                   border: 1px solid #3a5a70; border-radius: 999px; padding: 3px 12px; }}
  .wrap {{ max-width: 720px; margin: 0 auto; padding: 28px 16px 56px; }}
  .notice {{ background: #fff8e6; border: 1px solid #f0d48a; border-radius: 10px;
            padding: 12px 16px; font-size: 13px; color: #6b5200; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
          box-shadow: 0 2px 10px rgba(0,0,0,.06), 0 0 0 1px rgba(0,0,0,.04); }}
  .card-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }}
  .card-head .icon {{ width: 38px; height: 38px; border-radius: 10px; font-size: 19px;
                     display: flex; align-items: center; justify-content: center; color: #fff; }}
  .icon.red {{ background: linear-gradient(135deg, #d13438, #ff6b6b); }}
  .icon.blue {{ background: linear-gradient(135deg, #0078d4, #00bcf2); }}
  .icon.green {{ background: linear-gradient(135deg, #107c10, #4cc26b); }}
  .card-head h2 {{ font-size: 16px; margin: 0; }}
  .card-head .tag {{ font-size: 11px; color: #666; margin-top: 2px; }}
  .desc {{ color: #555; font-size: 13px; line-height: 1.7; margin: 8px 0 14px; }}
  .divider {{ border: 0; border-top: 1px dashed #ddd; margin: 18px 0; }}
  label {{ display: block; font-size: 13px; font-weight: 600; color: #333; margin: 14px 0 5px; }}
  input[type=text], input[type=email], input[type=password] {{
      width: 100%%; padding: 9px 12px; font-size: 14px; border: 1px solid #cfcfcf;
      border-radius: 8px; outline: none; transition: border-color .15s, box-shadow .15s; }}
  input:focus {{ border-color: #0078d4; box-shadow: 0 0 0 3px rgba(0,120,212,.15); }}
  input[readonly] {{ background: #f6f6f6; font-family: Consolas, monospace; color: #444; }}
  .btn {{ display: inline-block; border: 0; border-radius: 8px; padding: 10px 22px;
         font-size: 14px; cursor: pointer; margin-top: 16px; color: #fff;
         text-decoration: none; transition: filter .15s; }}
  .btn:hover {{ filter: brightness(1.08); }}
  .btn.red {{ background: #d13438; }}
  .btn.blue {{ background: #0078d4; }}
  .btn.green {{ background: #107c10; }}
  .btn.gray {{ background: #5a5a5a; }}
  .hint {{ color: #8a8a8a; font-size: 12px; margin-top: 4px; }}
  .result-icon {{ font-size: 40px; text-align: center; margin-bottom: 8px; }}
  .secret {{ display: block; background: #f6f6f6; border: 1px dashed #bbb; border-radius: 8px;
            padding: 14px 16px; font-family: Consolas, monospace; font-size: 17px;
            text-align: center; word-break: break-all; margin: 12px 0; }}
  .qr {{ text-align: center; margin: 14px 0; }}
  .qr img {{ border: 1px solid #e0e0e0; border-radius: 10px; padding: 8px; background: #fff; }}
  pre.debug {{ background: #1e1e1e; color: #9cdcfe; font-size: 12px; border-radius: 8px;
              padding: 12px 14px; overflow-x: auto; line-height: 1.6; }}
</style>
</head>
<body>
  <div class="topbar">
    <span class="dot"></span>
    <h1>团校积分系统 · 系统维护</h1>
    <span class="badge">仅本机 localhost 可访问</span>
  </div>
  <div class="wrap">
    <div class="notice">⚠️ 本页面集中维护三类敏感信息：<strong>system 密码、system 动态验证码（OTP）、
    邮件服务配置</strong>。它们不会出现在系统的任何其他页面或接口中。
    重置类操作立即生效，新密码与二维码只在结果页显示一次。</div>
    {content}
  </div>
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
        return _render(_result("⚠️", "表单已过期", "请返回维护页面重新操作。", False), 403)
    return None


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _result(icon: str, title: str, body_html: str, success: bool = True) -> str:
    color = "#107c10" if success else "#d13438"
    return f"""
    <div class="card">
      <div class="result-icon" style="color:{color}">{icon}</div>
      <h2 style="text-align:center;margin:0 0 14px;font-size:18px">{title}</h2>
      <div class="desc" style="margin-bottom:0">{body_html}</div>
      <div style="text-align:center">
        <a class="btn gray" href="/local/system">返回维护页面</a>
      </div>
    </div>
    """


def _console_content() -> str:
    token = _issue_form_token()

    password_card = f"""
    <div class="card">
      <div class="card-head">
        <span class="icon red">🔑</span>
        <div><h2>system 登录密码</h2><div class="tag">自定义新密码，或留空随机生成</div></div>
      </div>
      <p class="desc">重置内置管理员 <code>system</code> 的登录密码，旧密码立即失效。
      新密码仅在提交后的结果页显示一次。</p>
      <form method="post" action="/local/system/reset-password">
        <input type="hidden" name="form_token" value="{token}">
        <label for="new_password">新密码</label>
        <input type="password" id="new_password" name="new_password"
               placeholder="至少 {MIN_PASSWORD_LENGTH} 位；留空则随机生成强密码" autocomplete="new-password">
        <button class="btn red" type="submit">重置密码</button>
      </form>
    </div>
    """

    otp_card = f"""
    <div class="card">
      <div class="card-head">
        <span class="icon blue">🛡️</span>
        <div><h2>system 动态验证码（OTP）</h2><div class="tag">重新生成密钥并展示绑定二维码</div></div>
      </div>
      <p class="desc">登录除密码外还需验证器中的 6 位动态验证码。重置后旧验证器立即失效，
      请当场用验证器应用（Microsoft / Google Authenticator 或微信验证器小程序）扫码绑定。</p>
      <form method="post" action="/local/system/reset-otp">
        <input type="hidden" name="form_token" value="{token}">
        <button class="btn blue" type="submit">重置 OTP 并显示二维码</button>
      </form>
    </div>
    """

    config, saved_password = emailer.get_email_config()
    service_email = _esc(config.service_email) if config else ""
    suffix = _esc(config.student_email_suffix) if config else ""
    password_block = (
        f"""
        <label>当前已保存的密码/授权码（明文，仅此页面可见）</label>
        <input type="text" value="{_esc(saved_password)}" readonly>
        """
        if saved_password
        else '<p class="hint">尚未保存密码/授权码。</p>'
    )
    email_card = f"""
    <div class="card">
      <div class="card-head">
        <span class="icon green">✉️</span>
        <div><h2>邮件服务配置</h2><div class="tag">注册验证码、OTP 二维码与密码重置邮件的发件通道</div></div>
      </div>
      <p class="desc">QQ / 163 邮箱需使用 SMTP 授权码（不是登录密码）；
      Outlook 个人邮箱已禁用 SMTP，建议使用 QQ 或 163 邮箱。</p>
      <form method="post" action="/local/system/email-config">
        <input type="hidden" name="form_token" value="{token}">
        <label for="service_email">服务邮箱</label>
        <input type="email" id="service_email" name="service_email" value="{service_email}">
        {password_block}
        <label for="service_email_password">新密码/授权码</label>
        <input type="password" id="service_email_password" name="service_email_password"
               placeholder="留空保持不变">
        <label for="student_email_suffix">学生邮箱后缀</label>
        <input type="text" id="student_email_suffix" name="student_email_suffix"
               value="{suffix}" placeholder="@example.edu.cn">
        <button class="btn green" type="submit">保存邮箱配置</button>
      </form>
      <hr class="divider">
      <form method="post" action="/local/system/test-email">
        <input type="hidden" name="form_token" value="{token}">
        <label for="test_email">发送测试邮件到</label>
        <input type="email" id="test_email" name="test_email" placeholder="接收测试邮件的地址">
        <button class="btn gray" type="submit">发送测试邮件</button>
      </form>
    </div>
    """
    return password_card + otp_card + email_card


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
        return _render(_result("⚠️", "system 账号不存在", "请重启服务以自动创建。", False), 500)

    password = request.form.get("new_password", "")
    if password and len(password) < MIN_PASSWORD_LENGTH:
        return _render(
            _result("⚠️", "密码太短", f"自定义密码至少需要 {MIN_PASSWORD_LENGTH} 位字符。", False),
            400,
        )
    generated = not password
    if generated:
        password = secrets.token_urlsafe(12)
    admin.password_hash = hash_password_digest(client_password_digest(password))
    db.session.commit()
    source = "系统随机生成的强密码" if generated else "您自定义的密码"
    return _render(
        _result(
            "✅",
            "密码已重置",
            f"<p>{source}（仅显示这一次，请立即保存）：</p>"
            f'<span class="secret">{password}</span>'
            "<p>登录时还需要动态验证码；如未绑定或已失效，请返回维护页面重置 OTP。</p>",
        )
    )


@local_admin_bp.post("/local/system/reset-otp")
def reset_otp():
    error = _check_request()
    if error:
        return error
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        return _render(_result("⚠️", "system 账号不存在", "请重启服务以自动创建。", False), 500)
    secret, _uri = bind_new_totp(admin)
    db.session.commit()
    qr = qr_png_data_uri(provisioning_uri(secret, SYSTEM_ADMIN_ID))
    return _render(
        _result(
            "✅",
            "OTP 已重置",
            "<p>请立即用验证器应用扫码绑定，或手动输入下方密钥：</p>"
            f'<div class="qr"><img src="{qr}" alt="OTP 二维码" width="220" height="220"></div>'
            f'<span class="secret">{secret}</span>'
            "<p>此页面关闭后二维码与密钥无法再次查看。</p>",
        )
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
    return _render(_result("✅", "邮箱配置已保存", "注册验证码、OTP 与重置邮件将使用该配置发送。"))


@local_admin_bp.post("/local/system/test-email")
def test_email():
    error = _check_request()
    if error:
        return error
    address = request.form.get("test_email", "").strip()
    if not address:
        return _render(_result("⚠️", "缺少收件地址", "请输入接收测试邮件的地址。", False))
    success, message, debug_info = emailer.send_test_email(address, debug=True)
    debug_block = ""
    if debug_info:
        lines = "\n".join(_esc(line) for line in debug_info)
        debug_block = f"<pre class='debug'>{lines}</pre>"
    if success:
        return _render(_result("✅", "测试邮件发送成功", f"<p>已发送至 {_esc(address)}。</p>{debug_block}"))
    return _render(_result("❌", "测试邮件发送失败", f"<p>{_esc(message)}</p>{debug_block}", False))
