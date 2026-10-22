"""本机专用的系统维护控制台。

只能通过服务器本机（127.0.0.1 / ::1）访问 http://localhost:5000/local/system，
集中维护三类只允许出现在本机的敏感信息：
- 内置 system 管理员的密码（可自定义，留空则随机生成）；
- system 的 OTP（两步：生成候选二维码 → 输入验证码确认后才生效）；
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
from backend.services.otp_service import (
    begin_pending_otp,
    decode_pending_otp,
    revoke_trusted_devices,
    set_totp_secret,
)
from backend.utils.crypto import encrypt_secret
from backend.utils.otp import provisioning_uri, qr_png_data_uri, verify_totp
from backend.utils.passwords import client_password_digest, hash_password_digest


local_admin_bp = Blueprint("local_admin", __name__)

SYSTEM_ADMIN_ID = "system"
FORM_TOKEN_TTL_SECONDS = 600
MIN_PASSWORD_LENGTH = 8
_LOCAL_ADDRS = {"127.0.0.1", "::1", "localhost"}

# 与前端（React 页面）同一套设计语言：#f5f6f8 底、白色圆角卡片、灰色角色主题
_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>系统维护 · 团校积分系统</title>
<style>
  * {{ box-sizing: border-box; }}
  ::selection {{ background: rgba(96,96,96,.26); }}
  body {{ font-family: "Microsoft YaHei", "Segoe UI", system-ui, -apple-system, sans-serif;
         margin: 0; background: #f5f6f8; min-height: 100vh; color: #1f1f1f; }}
  .wrap {{ max-width: 896px; margin: 0 auto; padding: 24px 16px 56px; }}
  .page-header {{ display: flex; align-items: center; justify-content: space-between;
                 flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
  .page-header h1 {{ font-size: 24px; font-weight: 700; margin: 0; color: #424242; }}
  .badge {{ font-size: 12px; color: #616161; background: rgba(97,97,97,.08);
           border: 1px solid rgba(97,97,97,.25); border-radius: 999px; padding: 4px 12px; }}
  .notice {{ background: #fff; border: 1px solid rgba(209,52,56,.25); border-left: 4px solid #d13438;
            border-radius: 12px; padding: 14px 18px; font-size: 13px; color: #6b3a3c;
            line-height: 1.8; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  /* 页签：与学生/管理员页面同一组件样式（灰底胶囊、选中白色卡片） */
  .tabs > input {{ position: absolute; opacity: 0; pointer-events: none; }}
  .tabs-list {{ display: inline-flex; flex-wrap: wrap; gap: 4px; background: #ececec;
               border-radius: 10px; padding: 4px; margin-bottom: 16px; }}
  .tabs-list label {{ padding: 8px 16px; font-size: 14px; font-weight: 500; color: #555;
                     border-radius: 6px; cursor: pointer; transition: all .15s; }}
  #ctab-account:checked ~ .tabs-list label[for=ctab-account],
  #ctab-email:checked ~ .tabs-list label[for=ctab-email] {{
      background: #fff; color: #424242; box-shadow: 0 1px 2px rgba(0,0,0,.1); }}
  .panel {{ display: none; }}
  #ctab-account:checked ~ .panel-account {{ display: block; }}
  #ctab-email:checked ~ .panel-email {{ display: block; }}
  .card {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 16px;
          box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  .card h2 {{ font-size: 18px; font-weight: 600; margin: 0 0 4px; color: #525252; }}
  .card .sub {{ font-size: 12px; color: #999; margin: 0 0 12px; }}
  .desc {{ color: #616161; font-size: 13px; line-height: 1.8; margin: 8px 0 14px; }}
  .divider {{ border: 0; border-top: 1px solid #f0f0f0; margin: 20px 0; }}
  .field {{ margin-bottom: 16px; }}
  label {{ display: block; font-size: 14px; font-weight: 500; color: #333; margin: 0 0 6px; }}
  label .req {{ color: #d13438; }}
  input[type=text], input[type=email], input[type=password] {{
      width: 100%; height: 40px; padding: 8px 12px; font-size: 14px; border: 1px solid #d1d1d1;
      border-radius: 6px; outline: none; transition: border-color .15s, box-shadow .15s;
      background: #fff; color: #1f1f1f; }}
  input:focus {{ border-color: #616161; box-shadow: 0 0 0 2px rgba(97,97,97,.25); }}
  input[readonly] {{ background: #f5f5f5; font-family: Consolas, monospace; color: #444; }}
  .btn {{ display: inline-flex; align-items: center; justify-content: center; border: 0;
         border-radius: 6px; height: 36px; padding: 0 16px; font-size: 14px; font-weight: 500;
         cursor: pointer; color: #fff; text-decoration: none; transition: background .15s;
         box-shadow: 0 1px 2px rgba(0,0,0,.08); }}
  .btn.primary {{ background: #0078d4; }}
  .btn.primary:hover {{ background: #106ebe; }}
  .btn.red {{ background: #d13438; }}
  .btn.red:hover {{ background: #b52e31; }}
  .btn.green {{ background: #107c10; }}
  .btn.green:hover {{ background: #0d6b0d; }}
  .btn.gray {{ background: #fff; color: #1f1f1f; border: 1px solid #d1d1d1; box-shadow: none; }}
  .btn.gray:hover {{ background: #f5f5f5; }}
  .hint {{ color: #999; font-size: 12px; margin-top: 5px; }}
  .result-icon {{ width: 56px; height: 56px; border-radius: 50%; margin: 4px auto 14px;
                 display: flex; align-items: center; justify-content: center; font-size: 26px; color: #fff; }}
  .result-icon.ok {{ background: #107c10; }}
  .result-icon.bad {{ background: #d13438; }}
  .secret {{ display: block; background: #f5f5f5; border: 1px dashed #c8c8c8; border-radius: 6px;
            padding: 14px 16px; font-family: Consolas, monospace; font-size: 17px;
            text-align: center; word-break: break-all; margin: 12px 0; letter-spacing: 2px; }}
  .qr {{ text-align: center; margin: 16px 0; }}
  .qr img {{ border: 1px solid #e0e0e0; border-radius: 12px; padding: 10px; background: #fff;
            box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  pre.debug {{ background: #1e1e1e; color: #9cdcfe; font-size: 12px; border-radius: 6px;
              padding: 12px 14px; overflow-x: auto; line-height: 1.6; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="page-header">
      <h1>系统维护控制台</h1>
      <span class="badge">仅本机 localhost 可访问</span>
    </div>
    <div class="notice">⚠️ 本页面集中维护三类敏感信息：<strong>system 密码、system 动态验证码（OTP）、
    邮件服务配置</strong>。它们不会出现在系统的任何其他页面或接口中。
    新密码与二维码只在结果页显示一次；OTP 需当场输入验证码确认后才会生效。</div>
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
        return _render(_result("表单已过期", "请返回维护页面重新操作。", False), 403)
    return None


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _result(title: str, body_html: str, success: bool = True) -> str:
    icon_class = "ok" if success else "bad"
    icon = "✓" if success else "✕"
    return f"""
    <div class="card" style="max-width:560px;margin:0 auto">
      <div class="result-icon {icon_class}">{icon}</div>
      <h2 style="text-align:center;margin:0 0 14px;font-size:18px">{title}</h2>
      <div class="desc" style="margin-bottom:0">{body_html}</div>
      <div style="text-align:center;margin-top:16px">
        <a class="btn gray" href="/local/system">返回维护页面</a>
      </div>
    </div>
    """


def _console_content() -> str:
    token = _issue_form_token()

    password_card = f"""
    <div class="card">
      <h2>system 登录密码</h2>
      <p class="sub">自定义新密码，或留空随机生成</p>
      <p class="desc">重置内置管理员 <code>system</code> 的登录密码，旧密码立即失效。
      新密码仅在提交后的结果页显示一次。</p>
      <form method="post" action="/local/system/reset-password">
        <input type="hidden" name="form_token" value="{token}">
        <div class="field">
          <label for="new_password">新密码</label>
          <input type="password" id="new_password" name="new_password"
                 placeholder="至少 {MIN_PASSWORD_LENGTH} 位；留空则随机生成强密码" autocomplete="new-password">
        </div>
        <button class="btn red" type="submit">重置密码</button>
      </form>
    </div>
    """

    otp_card = f"""
    <div class="card">
      <h2>system 动态验证码（OTP）</h2>
      <p class="sub">扫码并输入验证码确认后才生效</p>
      <p class="desc">登录除密码外还需验证器中的 6 位动态验证码。点击后将生成候选二维码，
      用验证器应用（Microsoft / Google Authenticator 或微信验证器小程序）扫码并输入验证码确认，
      新 OTP 才会替换旧的；中途放弃则原有 OTP 保持不变。</p>
      <form method="post" action="/local/system/reset-otp">
        <input type="hidden" name="form_token" value="{token}">
        <button class="btn primary" type="submit">生成新的 OTP 二维码</button>
      </form>
    </div>
    """

    config, saved_password = emailer.get_email_config()
    service_email = _esc(config.service_email) if config else ""
    suffix = _esc(config.student_email_suffix) if config else ""
    password_block = (
        f"""
        <div class="field">
          <label>当前已保存的密码/授权码（明文，仅此页面可见）</label>
          <input type="text" value="{_esc(saved_password)}" readonly>
        </div>
        """
        if saved_password
        else '<p class="hint">尚未保存密码/授权码。</p>'
    )
    email_card = f"""
    <div class="card">
      <h2>邮件服务配置</h2>
      <p class="sub">注册验证码、OTP 二维码与重置邮件的发件通道</p>
      <p class="desc">QQ / 163 邮箱需使用 SMTP 授权码（不是登录密码）；
      Outlook 个人邮箱已禁用 SMTP，建议使用 QQ 或 163 邮箱。</p>
      <form method="post" action="/local/system/email-config">
        <input type="hidden" name="form_token" value="{token}">
        <div class="field">
          <label for="service_email">服务邮箱</label>
          <input type="email" id="service_email" name="service_email" value="{service_email}">
        </div>
        {password_block}
        <div class="field">
          <label for="service_email_password">新密码/授权码</label>
          <input type="password" id="service_email_password" name="service_email_password"
                 placeholder="留空保持不变">
        </div>
        <div class="field">
          <label for="student_email_suffix">学生邮箱后缀</label>
          <input type="text" id="student_email_suffix" name="student_email_suffix"
                 value="{suffix}" placeholder="@example.edu.cn">
        </div>
        <button class="btn green" type="submit">保存邮箱配置</button>
      </form>
      <hr class="divider">
      <form method="post" action="/local/system/test-email">
        <input type="hidden" name="form_token" value="{token}">
        <div class="field">
          <label for="test_email">发送测试邮件到</label>
          <input type="email" id="test_email" name="test_email" placeholder="接收测试邮件的地址">
        </div>
        <button class="btn gray" type="submit">发送测试邮件</button>
      </form>
    </div>
    """
    return (
        '<div class="tabs">'
        '<input type="radio" name="console-tab" id="ctab-account" checked>'
        '<input type="radio" name="console-tab" id="ctab-email">'
        '<div class="tabs-list">'
        '<label for="ctab-account">账号安全（密码 / OTP）</label>'
        '<label for="ctab-email">邮件服务</label>'
        "</div>"
        f'<div class="panel panel-account">{password_card}{otp_card}</div>'
        f'<div class="panel panel-email">{email_card}</div>'
        "</div>"
    )


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
        return _render(_result("system 账号不存在", "请重启服务以自动创建。", False), 500)

    password = request.form.get("new_password", "")
    if password and len(password) < MIN_PASSWORD_LENGTH:
        return _render(
            _result("密码太短", f"自定义密码至少需要 {MIN_PASSWORD_LENGTH} 位字符。", False),
            400,
        )
    generated = not password
    if generated:
        password = secrets.token_urlsafe(12)
    admin.password_hash = hash_password_digest(client_password_digest(password))
    # 重置 system 密码后：旧令牌与"免 OTP"信任记录全部失效
    admin.token_version = (admin.token_version or 0) + 1
    revoke_trusted_devices(admin)
    db.session.commit()
    source = "系统随机生成的强密码" if generated else "您自定义的密码"
    return _render(
        _result(
            "密码已重置",
            f"<p>{source}（仅显示这一次，请立即保存）：</p>"
            f'<span class="secret">{password}</span>'
            "<p>登录时还需要动态验证码；如未绑定或已失效，请返回维护页面重置 OTP。</p>",
        )
    )


@local_admin_bp.post("/local/system/reset-otp")
def reset_otp():
    """第一步：生成候选二维码（不生效），等待验证码确认。"""
    error = _check_request()
    if error:
        return error
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        return _render(_result("system 账号不存在", "请重启服务以自动创建。", False), 500)

    ticket, candidate = begin_pending_otp(admin, "admin", "local_system_reset")
    qr = qr_png_data_uri(provisioning_uri(candidate, SYSTEM_ADMIN_ID))
    fresh_token = _issue_form_token()
    content = f"""
    <div class="card" style="max-width:560px;margin:0 auto">
      <h2>绑定新的 system OTP</h2>
      <p class="sub">确认前原有 OTP 仍然有效</p>
      <p class="desc">请用验证器应用扫描下方二维码，或手动输入密钥：</p>
      <div class="qr"><img src="{qr}" alt="OTP 二维码" width="220" height="220"></div>
      <span class="secret">{candidate}</span>
      <form method="post" action="/local/system/reset-otp/confirm">
        <input type="hidden" name="form_token" value="{fresh_token}">
        <input type="hidden" name="bind_ticket" value="{_esc(ticket)}">
        <div class="field">
          <label for="otp_code">输入验证器中显示的 6 位验证码以确认生效 <span class="req">*</span></label>
          <input type="text" id="otp_code" name="otp_code" inputmode="numeric" maxlength="6"
                 autocomplete="one-time-code" placeholder="6 位数字"
                 style="text-align:center;letter-spacing:8px;text-indent:8px;font-size:18px">
        </div>
        <button class="btn primary" type="submit" style="width:100%">验证并生效</button>
      </form>
      <div style="text-align:center;margin-top:12px">
        <a class="btn gray" href="/local/system">放弃（保持原有 OTP）</a>
      </div>
    </div>
    """
    return _render(content)


@local_admin_bp.post("/local/system/reset-otp/confirm")
def confirm_reset_otp():
    """第二步：验证码证明候选密钥已被扫码收录，此时才写入。"""
    error = _check_request()
    if error:
        return error
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        return _render(_result("system 账号不存在", "请重启服务以自动创建。", False), 500)

    ticket = request.form.get("bind_ticket", "")
    code = request.form.get("otp_code", "").strip()
    claims, decode_error = decode_pending_otp(ticket)
    if (
        claims is None
        or claims.get("purpose") != "local_system_reset"
        or claims.get("sub") != SYSTEM_ADMIN_ID
    ):
        return _render(_result("绑定请求无效或已过期", decode_error or "请返回维护页面重新生成二维码。", False), 400)
    if not verify_totp(claims["candidate_secret"], code):
        return _render(
            _result("验证码错误", "请确认已扫描最新二维码，然后返回重新生成并立即输入验证码。", False),
            400,
        )

    set_totp_secret(admin, claims["candidate_secret"])
    db.session.commit()
    return _render(
        _result("OTP 已生效", "<p>新的动态验证码已绑定成功，旧验证器立即失效。下次登录请使用新验证码。</p>")
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
    return _render(_result("邮箱配置已保存", "注册验证码、OTP 与重置邮件将使用该配置发送。"))


@local_admin_bp.post("/local/system/test-email")
def test_email():
    error = _check_request()
    if error:
        return error
    address = request.form.get("test_email", "").strip()
    if not address:
        return _render(_result("缺少收件地址", "请输入接收测试邮件的地址。", False))
    success, message, debug_info = emailer.send_test_email(address, debug=True)
    debug_block = ""
    if debug_info:
        lines = "\n".join(_esc(line) for line in debug_info)
        debug_block = f"<pre class='debug'>{lines}</pre>"
    if success:
        return _render(_result("测试邮件发送成功", f"<p>已发送至 {_esc(address)}。</p>{debug_block}"))
    return _render(_result("测试邮件发送失败", f"<p>{_esc(message)}</p>{debug_block}", False))
