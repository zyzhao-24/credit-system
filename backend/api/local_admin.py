"""本机专用的 system 账号维护控制台。

只能通过服务器本机（127.0.0.1 / ::1）访问 http://localhost:5000/local/system，
用于首次部署或找回场景下维护内置 system 管理员的密码与 OTP，
不需要在服务器上运行任何命令行脚本。

安全措施：
- 非本机来源一律 404（不暴露页面存在）；
- 页面签发短时表单令牌（HMAC 签名，10 分钟有效），阻止其他网站跨站表单提交；
- 密码只能随机生成、只在结果页显示一次，不接受外部指定值（避免 CSRF 强设口令）；
- 拒绝跨站浏览器请求（Sec-Fetch-Site 标头存在且非同源时直接拒绝）。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from flask import Blueprint, current_app, request

from backend.extensions import db
from backend.models import Admin
from backend.services.otp_service import bind_new_totp
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
<title>系统账号维护（本机专用）</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; background: #f3f3f3; margin: 0;
         display: flex; justify-content: center; padding: 40px 16px; }}
  main {{ background: #fff; border-radius: 12px; padding: 32px; max-width: 520px;
         width: 100%%; box-shadow: 0 8px 32px rgba(0,0,0,.08); }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .warn {{ background: #fff4ce; border-left: 4px solid #ca5010; padding: 10px 14px;
          font-size: 13px; border-radius: 4px; margin-bottom: 20px; }}
  section {{ border-top: 1px solid #e0e0e0; padding-top: 16px; margin-top: 16px; }}
  h2 {{ font-size: 16px; margin: 0 0 6px; }}
  p.desc {{ color: #555; font-size: 13px; margin: 0 0 12px; }}
  button {{ background: #d13438; color: #fff; border: 0; border-radius: 6px;
          padding: 10px 20px; font-size: 14px; cursor: pointer; }}
  button:hover {{ background: #b52b2f; }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
<main>
  <h1>系统账号维护</h1>
  <p class="sub">本页面仅允许在服务器本机（localhost）访问，用于维护内置 system 管理员。</p>
  <div class="warn">⚠️ 两个操作都会立即生效：旧密码/旧验证器将立即失效，
  新密码与二维码只会在提交后的页面显示一次。</div>
  {content}
</main>
</body>
</html>
"""

_ACTIONS = """
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


@local_admin_bp.get("/local/system")
def console():
    error = _check_request()
    if error:
        return error
    return _render(_ACTIONS.format(token=_issue_form_token()))


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
