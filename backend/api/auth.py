"""Authentication and public student registration API.

Login is a mandatory two-step flow: password first, TOTP code second.
Step 1 returns a short-lived otp_ticket (10 minutes) which step 2 exchanges
for the real access token.

OTP 验证成功后，账号会信任当时的设备浏览器（HttpOnly+Secure Cookie），
信任期内同一设备再次登录时第一步直接发令牌，不再索要 OTP。不按来源 IP
信任：校园 NAT/VPN 下同出口 IP 的用户会互相"继承"免 OTP 状态，等同
绕过动态验证码。
"""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from backend.auth.decorators import require_auth, require_admin
from backend.auth.jwt import decode_token, issue_token
from backend.extensions import db
from backend.models import Admin, EmailVerification, Student, TrustedDevice
from backend.services import mail_templates
from backend.services.emailer import send_email
from backend.services.otp_service import (
    bind_new_totp,
    begin_pending_otp,
    check_totp,
    confirm_pending_otp,
    decode_pending_otp,
    has_totp,
    pending_otp_bundle,
    revoke_trusted_devices,
    send_totp_binding_email,
    set_totp_secret,
    student_email_address,
)
from backend.services.students import PHONE_PATTERN, create_student
from backend.utils.passwords import (
    client_password_digest,
    hash_password_digest,
    verify_password_digest,
)


auth_bp = Blueprint("auth", __name__)
PASSWORD_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RESET_WINDOW_SECONDS = 600
_RESET_MAX_ATTEMPTS = 3
_reset_attempts: dict[str, list[float]] = {}
_reset_lock = threading.Lock()

OTP_TICKET_SECONDS = 600
# OTP 信任期：验证成功后 3 天内同设备浏览器免 OTP
TRUSTED_DEVICE_DAYS = 3
TRUSTED_DEVICE_COOKIE = "trusted_device"

# ---- 登录/动态码防爆破限速 ----
# 键带真实客户端 IP（tls_proxy 覆盖写入 X-Forwarded-For + ProxyFix 恢复），
# 硬限速在校验之前：超限直接 429，不再消耗 PBKDF2 算力；攻击者只会锁死
# "自己 IP + 受害账号"这个组合，不影响其他来源的正常用户。
# 全部计数字典有上限（RATE_LIMIT_MAX_KEYS 配置项），防止随机用户名撑大内存。
_login_failures: dict[str, list[float]] = {}
_login_lock = threading.Lock()
_global_failures: list[float] = []
_otp_failures: dict[str, list[float]] = {}
_otp_ticket_failures: dict[str, int] = {}
_ticket_issues: dict[str, list[float]] = {}
_otp_lock = threading.Lock()


def _limit_config(name: str, default: int) -> int:
    return int(current_app.config.get(name, default))


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _windowed(d: dict[str, list[float]], key: str, window: int, now: float) -> list[float]:
    """取出 key 在时间窗内的记录并惰性清理过期项。"""
    stamps = [item for item in d.get(key, []) if now - item < window]
    if stamps:
        d[key] = stamps
    else:
        d.pop(key, None)
    return stamps


def _bounded_set(d: dict, key: str, value) -> None:
    """有界写入：达到上限时丢弃最旧的键（dict 保插入序），防止内存被撑大。"""
    if key not in d and len(d) >= _limit_config("RATE_LIMIT_MAX_KEYS", 100_000):
        oldest = next(iter(d), None)
        if oldest is not None:
            d.pop(oldest, None)
    d[key] = value


def _login_rate_limited(ip_key: str, acct_key: str) -> bool:
    """硬限速（只读判断，不计数）：(IP+账号) 与 (IP) 两个维度。"""
    now = time.time()
    with _login_lock:
        stamps = _windowed(_login_failures, acct_key, 3600, now)
        if sum(1 for item in stamps if now - item < 60) >= _limit_config(
            "LOGIN_FAIL_MAX_PER_MINUTE", 5
        ):
            return True
        if len(stamps) >= _limit_config("LOGIN_FAIL_MAX_PER_HOUR", 20):
            return True
        ip_stamps = _windowed(_login_failures, ip_key, 3600, now)
        if sum(1 for item in ip_stamps if now - item < 60) >= _limit_config(
            "LOGIN_IP_FAIL_MAX_PER_MINUTE", 50
        ):
            return True
        return len(ip_stamps) >= _limit_config("LOGIN_IP_FAIL_MAX_PER_HOUR", 300)


def _record_login_failure(ip_key: str, acct_key: str) -> float:
    """记录一次密码失败（IP+账号、IP、全站三个桶），返回全站拥挤需要的延迟秒数。"""
    now = time.time()
    with _login_lock:
        for key in (ip_key, acct_key):
            stamps = _windowed(_login_failures, key, 3600, now)
            stamps.append(now)
            _bounded_set(_login_failures, key, stamps)
        global _global_failures
        _global_failures = [item for item in _global_failures if now - item < 60]
        _global_failures.append(now)
        crowded = len(_global_failures) > _limit_config("LOGIN_GLOBAL_FAIL_PER_MINUTE", 120)
    # 全站失败拥挤（分布式撞库特征）：统一加延迟拖慢吞吐，但不拒绝
    return float(_limit_config("LOGIN_GLOBAL_FAIL_DELAY_SECONDS", 2)) if crowded else 0.0


def _clear_login_failures(ip_key: str, acct_key: str) -> None:
    with _login_lock:
        _login_failures.pop(acct_key, None)
        _login_failures.pop(ip_key, None)


def _ticket_issue_limited(account_key: str) -> bool:
    """otp_ticket 签发限速：成功也计数，防止"取票→试 5 次→再取票"循环爆破。"""
    now = time.time()
    with _otp_lock:
        stamps = _windowed(_ticket_issues, account_key, 60, now)
        if len(stamps) >= _limit_config("OTP_TICKET_MAX_PER_MINUTE", 3):
            return True
        stamps.append(now)
        _bounded_set(_ticket_issues, account_key, stamps)
    return False


def _too_many_requests(message: str = "尝试次数过多，请稍后再试"):
    return jsonify({"detail": message}), 429, {"Retry-After": "60"}
_VERIFY_CODE_TTL_MINUTES = 10
_VERIFY_CODE_MAX_ATTEMPTS = 5
_VERIFY_CODE_WINDOW_SECONDS = 600
_VERIFY_CODE_MAX_SENDS = 3
_code_sends: dict[str, list[float]] = {}
_code_lock = threading.Lock()


def _json_error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _resolve_user_type(username: str, requested: str) -> str | None:
    if requested in {"student", "admin"}:
        return requested
    if not requested:
        return "student" if username.isdigit() else "admin"
    return None


def _load_account(user_type: str, username: str) -> Student | Admin | None:
    if user_type == "student":
        return db.session.get(Student, username)
    return db.session.get(Admin, username)


# 对不存在的账号也执行一次等价 PBKDF2，消除"账号是否存在"的计时侧信道
# （存在与否的响应时间曾相差一个数量级：~200ms vs ~20ms）
_DUMMY_HASH = hash_password_digest("0" * 64)


def _check_password(user_type: str, username: str, password_digest: str) -> Student | Admin | None:
    if not PASSWORD_DIGEST_PATTERN.fullmatch(password_digest):
        return None
    account = _load_account(user_type, username)
    if account is None:
        verify_password_digest(_DUMMY_HASH, password_digest)
        return None
    if not verify_password_digest(account.password_hash, password_digest):
        return None
    return account


def _identity_for(account: Student | Admin, user_type: str) -> dict[str, Any]:
    if user_type == "student":
        assert isinstance(account, Student)
        return {
            "id": account.student_id,
            "user_type": "student",
            "name": account.name,
            "role": "",
            "department": "",
            "tv": account.token_version,
            "password_reset_required": bool(account.password_reset_required),
        }
    assert isinstance(account, Admin)
    return {
        "id": account.admin_id,
        "user_type": "admin",
        "name": account.admin_id,
        "role": account.role,
        "department": account.department,
        "tv": account.token_version,
        "password_reset_required": bool(account.password_reset_required),
    }


def _issue_otp_ticket(account: Student | Admin, user_type: str) -> str:
    account_id = account.student_id if isinstance(account, Student) else account.admin_id
    ticket_identity = {
        "id": account_id,
        "user_type": user_type,
        "name": "",
        "role": "otp_pending",
        "department": "",
    }
    return issue_token(ticket_identity, current_app.config["SECRET_KEY"], OTP_TICKET_SECONDS)


def _token_payload(identity: dict[str, Any]) -> dict[str, Any]:
    expires = int(current_app.config["JWT_EXPIRES_SECONDS"])
    token = issue_token(identity, current_app.config["SECRET_KEY"], expires)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires,
        "user_type": identity["user_type"],
        "role": identity.get("role", ""),
        "department": identity.get("department", ""),
        "name": identity.get("name", ""),
        "password_reset_required": bool(identity.get("password_reset_required", False)),
    }


def _account_id_of(account: Student | Admin) -> str:
    return account.student_id if isinstance(account, Student) else account.admin_id


def _device_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _trusted_login(account: Student | Admin, user_type: str) -> bool:
    """该账号在当前设备浏览器上是否处于 OTP 信任期内（仅认设备 Cookie）。

    不按来源 IP 信任：校园 NAT/VPN 下同出口 IP 的用户会互相"继承"
    免 OTP 状态，等同绕过动态验证码。顺带惰性清理过期信任记录。
    """
    now = datetime.now()
    rows = TrustedDevice.query.filter_by(
        user_type=user_type, account_id=_account_id_of(account)
    ).all()
    expired = [row for row in rows if row.expires_at <= now]
    for row in expired:
        db.session.delete(row)
    if expired:
        db.session.commit()
    active = [row for row in rows if row.expires_at > now]
    if not active:
        return False
    cookie_token = request.cookies.get(TRUSTED_DEVICE_COOKIE, "")
    if not cookie_token:
        return False
    token_hash = _device_token_hash(cookie_token)
    return any(row.token_hash == token_hash for row in active)


def _remember_trusted_device(account: Student | Admin, user_type: str) -> str:
    """OTP 验证成功后调用：写入信任记录，返回要发给浏览器的设备令牌。

    ip 字段记录真实来源地址（经 XFF 恢复），仅作审计信息，不参与信任匹配。
    """
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    db.session.add(
        TrustedDevice(
            user_type=user_type,
            account_id=_account_id_of(account),
            token_hash=_device_token_hash(token),
            ip=request.remote_addr or "",
            created_at=now,
            expires_at=now + timedelta(days=TRUSTED_DEVICE_DAYS),
        )
    )
    db.session.commit()
    return token


def _otp_required_response(account: Student | Admin, user_type: str):
    """Start the OTP step: bind-and-email students who have no secret yet."""
    if not has_totp(account):
        if isinstance(account, Student):
            secret, _uri = bind_new_totp(account)
            db.session.commit()
            success, message = send_totp_binding_email(account, secret)
            if not success:
                return _json_error(f"OTP绑定邮件发送失败：{message}")
            ticket = _issue_otp_ticket(account, user_type)
            return jsonify(
                {
                    "success": True,
                    "otp_required": True,
                    "otp_ticket": ticket,
                    "message": message,
                }
            )
        # 管理员（无邮箱）未绑定 OTP 时不允许登录：
        # 普通管理员由系统管理员在后台"重置 OTP"中转二维码；
        # system 账号只能在服务器本机 /local/system 初始化。
        if account.admin_id == "system":
            return _json_error(
                "system 账号尚未绑定动态验证码，请在服务器本机访问 "
                "http://localhost:5000/local/system 完成初始化",
                403,
            )
        return _json_error(
            "该管理员账号尚未绑定动态验证码，请联系系统管理员在后台"
            "「系统设置 → 管理员账号 → 重置 OTP」生成二维码并转交给您",
            403,
        )
    ticket = _issue_otp_ticket(account, user_type)
    return jsonify(
        {
            "success": True,
            "otp_required": True,
            "otp_ticket": ticket,
            "message": "请输入验证器中的6位动态验证码",
        }
    )


@auth_bp.post("/api/auth/token")
def oauth2_token():
    """OAuth2 Password-compatible token endpoint (step 1: password).

    The password field carries the client-side SHA-256 digest for compatibility
    with the legacy UI. A correct password yields an otp_ticket, not an access
    token; the OTP code is exchanged at /api/auth/token/verify.
    """
    form = request.form
    grant_type = form.get("grant_type", "password")
    username = form.get("username", "").strip()
    password_digest = form.get("password", "").strip().lower()
    requested_type = form.get("user_type", "").strip()

    if grant_type != "password" or not username or not password_digest:
        return jsonify({"detail": "无效的登录请求"}), 400

    user_type = _resolve_user_type(username, requested_type)
    if user_type is None:
        return jsonify({"detail": "无效的用户类型"}), 400

    ip_key = f"ip:{_client_ip()}"
    acct_key = f"{_client_ip()}:{user_type}:{username}"
    # 硬限速在校验之前：超限直接 429，不消耗 PBKDF2 算力
    if _login_rate_limited(ip_key, acct_key):
        return _too_many_requests()

    try:
        account = _check_password(user_type, username, password_digest)
    except Exception:
        db.session.rollback()
        raise
    if account is None:
        delay = _record_login_failure(ip_key, acct_key)
        if delay:
            time.sleep(delay)
        return jsonify({"detail": "账号或密码错误"}), 401
    _clear_login_failures(ip_key, acct_key)
    # 信任期内验证过 OTP 的设备：直接发令牌，不再索要 OTP
    if _trusted_login(account, user_type):
        identity = _identity_for(account, user_type)
        return jsonify({"success": True, **_token_payload(identity)})
    # otp_ticket 签发限速（成功也计数）：防止"取票→试 5 次→再取票"循环爆破
    if _ticket_issue_limited(f"{user_type}:{username}"):
        return _too_many_requests("登录尝试过于频繁，请稍后再试")
    return _otp_required_response(account, user_type)


@auth_bp.post("/api/auth/token/verify")
def oauth2_token_verify():
    """Step 2: exchange otp_ticket + TOTP code for the real access token."""
    data = request.get_json(silent=True) or {}
    ticket = data.get("otp_ticket", "").strip()
    code = data.get("otp_code", "").strip()
    if not ticket or not code:
        return _json_error("请输入动态验证码")

    try:
        claims = decode_token(ticket, current_app.config["SECRET_KEY"])
    except Exception:
        return _json_error("验证已过期，请重新登录", 401)
    if claims.get("role") != "otp_pending":
        return _json_error("无效的验证票据", 401)

    user_type = claims.get("user_type", "")
    account_id = claims.get("sub", "")
    account = _load_account(user_type, account_id)

    # 防爆破：同一票据失败达到上限即作废（票据需正确密码才能获取，不构成
    # 锁定 DoS）；账号级限速采用软限速——先验码，429 只发给错误且超限的尝试
    ticket_key = _device_token_hash(ticket)
    account_key = f"{user_type}:{account_id}"
    now = time.time()
    with _otp_lock:
        ticket_dead = _otp_ticket_failures.get(ticket_key, 0) >= _limit_config(
            "OTP_FAIL_MAX_PER_TICKET", 5
        )
    if ticket_dead:
        return _json_error("验证码错误次数过多，请重新登录", 401)

    if account is None or not check_totp(account, code):
        with _otp_lock:
            _bounded_set(
                _otp_ticket_failures,
                ticket_key,
                _otp_ticket_failures.get(ticket_key, 0) + 1,
            )
            stamps = [item for item in _otp_failures.get(account_key, []) if now - item < 60]
            stamps.append(now)
            _bounded_set(_otp_failures, account_key, stamps)
            over_limit = len(stamps) > _limit_config("OTP_FAIL_MAX_PER_MINUTE", 10)
        if over_limit:
            return _too_many_requests("验证码尝试过于频繁，请稍后再试")
        return _json_error("验证码错误，请重新输入")

    with _otp_lock:
        _otp_ticket_failures.pop(ticket_key, None)
        _otp_failures.pop(account_key, None)

    try:
        identity = _identity_for(account, user_type)
        device_token = _remember_trusted_device(account, user_type)
    except Exception:
        db.session.rollback()
        raise
    response = jsonify({"success": True, **_token_payload(identity)})
    # 设备令牌：信任期内该设备浏览器登录免 OTP；HttpOnly 防 JS 读取，Secure 仅加密传输
    response.set_cookie(
        TRUSTED_DEVICE_COOKIE,
        device_token,
        max_age=TRUSTED_DEVICE_DAYS * 86400,
        httponly=True,
        samesite="Lax",
        secure=True,
    )
    return response


def _legacy_login(user_type: str):
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password_digest = data.get("password_hash", "").strip().lower()
    ip_key = f"ip:{_client_ip()}"
    acct_key = f"{_client_ip()}:{user_type}:{username}"
    if _login_rate_limited(ip_key, acct_key):
        return _too_many_requests()
    account = _check_password(user_type, username, password_digest)
    if account is None:
        delay = _record_login_failure(ip_key, acct_key)
        if delay:
            time.sleep(delay)
        return _json_error("学号或密码错误" if user_type == "student" else "账号或密码错误")
    _clear_login_failures(ip_key, acct_key)
    if _trusted_login(account, user_type):
        identity = _identity_for(account, user_type)
        return jsonify({"success": True, **_token_payload(identity)})
    if _ticket_issue_limited(f"{user_type}:{username}"):
        return _too_many_requests("登录尝试过于频繁，请稍后再试")
    return _otp_required_response(account, user_type)


@auth_bp.post("/api/login/student")
def legacy_student_login():
    return _legacy_login("student")


@auth_bp.post("/api/login/admin")
def legacy_admin_login():
    return _legacy_login("admin")


@auth_bp.get("/api/auth/me")
@require_auth
def auth_me():
    identity = g.current_identity
    return jsonify({"success": True, "user": identity})


@auth_bp.post("/api/auth/logout")
@auth_bp.post("/api/logout")
@require_auth
def auth_logout():
    """服务端登出：令牌版本 +1，该账号此前签发的所有访问令牌立即失效。"""
    account = getattr(g, "current_account", None)
    if account is not None:
        account.token_version = (account.token_version or 0) + 1
        db.session.commit()
    return jsonify({"success": True})


@auth_bp.get("/api/admin/session_info")
@require_admin
def admin_session_info():
    identity = g.current_identity
    return jsonify(
        {
            "success": True,
            "admin_id": identity.get("sub", ""),
            "role": identity.get("role", "admin"),
            "department": identity.get("department", ""),
        }
    )


# ========== 注册邮箱验证码 ==========


def _code_send_limited(key: str) -> bool:
    now = time.time()
    with _code_lock:
        sends = [item for item in _code_sends.get(key, []) if now - item < _VERIFY_CODE_WINDOW_SECONDS]
        if len(sends) >= _VERIFY_CODE_MAX_SENDS:
            _code_sends[key] = sends
            return True
        sends.append(now)
        _code_sends[key] = sends
    return False


def _verification_email_bodies(name: str, code: str, scene: str) -> tuple[str, str]:
    plain = f"""
您好，{name} 同学：

您正在{scene}团校积分系统账号，邮箱验证码为：

    {code}

验证码 {_VERIFY_CODE_TTL_MINUTES} 分钟内有效，请勿泄露给他人。

如非本人操作，请忽略本邮件。

---
团校积分系统
"""
    html = mail_templates.render_mail_html(
        f"{scene}验证码",
        mail_templates.greeting(name)
        + mail_templates.paragraph(f"您正在{scene}团校积分系统账号，邮箱验证码为：")
        + mail_templates.code_block(code)
        + mail_templates.hint(f"验证码 {_VERIFY_CODE_TTL_MINUTES} 分钟内有效，请勿泄露给他人。"),
    )
    return plain, html


def _send_email_code(student_id: str, name: str, scene: str) -> tuple[bool, str]:
    """向学号邮箱发送6位验证码并落库（注册/忘记密码共用）。"""
    address, error = student_email_address(student_id)
    if address is None:
        return False, error
    code = f"{secrets.randbelow(1000000):06d}"
    plain, html = _verification_email_bodies(name, code, scene)
    success, message = send_email(address, f"团校积分系统 - {scene}验证码", plain, html=html)
    if not success:
        return False, message

    verification = db.session.get(EmailVerification, student_id)
    if verification is None:
        verification = EmailVerification(student_id=student_id, created_at=datetime.now())
        db.session.add(verification)
    verification.code_hash = hash_password_digest(code)
    verification.expires_at = datetime.now() + timedelta(minutes=_VERIFY_CODE_TTL_MINUTES)
    verification.attempts = 0
    verification.created_at = datetime.now()
    db.session.commit()
    return True, f"验证码已发送至 {address}，{_VERIFY_CODE_TTL_MINUTES}分钟内有效"


@auth_bp.post("/api/student/register/send_code")
def send_registration_code():
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "").strip()
    name = data.get("name", "").strip()

    if not student_id or not name:
        return _json_error("请先填写学号和姓名")
    if not student_id.isdigit():
        return _json_error("学号只能包含数字")
    if db.session.get(Student, student_id):
        return _json_error("该学号已注册，请直接登录")

    rate_key = f"register:{student_id}:{request.remote_addr or 'unknown'}"
    if _code_send_limited(rate_key):
        return _json_error("验证码请求过于频繁，请稍后再试", 429)

    success, message = _send_email_code(student_id, name, "注册")
    if not success:
        return _json_error(message)
    return jsonify({"success": True, "message": message})


def _check_registration_code(student_id: str, code: str) -> str | None:
    """Return an error message, or None when the code is valid."""
    verification = db.session.get(EmailVerification, student_id)
    if verification is None:
        return "请先获取邮箱验证码"
    if datetime.now() > verification.expires_at:
        return "验证码已过期，请重新获取"
    if verification.attempts >= _VERIFY_CODE_MAX_ATTEMPTS:
        return "验证码尝试次数过多，请重新获取"
    if not verify_password_digest(verification.code_hash, code.strip()):
        verification.attempts += 1
        db.session.commit()
        return "验证码错误"
    db.session.delete(verification)
    return None


@auth_bp.post("/api/student/register")
def student_register():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    student_id = data.get("student_id", "").strip()
    phone = data.get("phone", "").strip()
    wechat = data.get("wechat", "").strip()
    password = data.get("password", "")
    password_digest = data.get("password_hash", "").strip().lower()
    suggestion = data.get("suggestion", "").strip()
    email_code = data.get("email_code", "").strip()

    if not all([name, student_id, phone, wechat, password or password_digest]):
        return _json_error("请填写所有必填项")
    if not student_id.isdigit():
        return _json_error("学号只能包含数字")
    if db.session.get(Student, student_id):
        return _json_error("该学号已注册，请直接登录")
    if not PHONE_PATTERN.fullmatch(phone):
        return _json_error("请输入正确的手机号码")
    if password and len(password) < 6:
        return _json_error("密码至少需要6位字符")
    if password_digest and not PASSWORD_DIGEST_PATTERN.fullmatch(password_digest):
        return _json_error("密码格式不正确")
    if not email_code:
        return _json_error("请输入邮箱验证码")

    code_error = _check_registration_code(student_id, email_code)
    if code_error:
        return _json_error(code_error)

    try:
        student = create_student(
            student_id,
            name,
            password_digest or client_password_digest(password),
            password_is_digest=True,
        )
        student.phone = phone
        student.wechat = wechat
        student.suggestion = suggestion
        student.info_updated_at = datetime.now()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # 注册成功后再绑定 OTP：候选密钥随响应一次性返回，学生在弹窗中扫码并
    # 输入验证码确认后才真正生效；中途放弃则保持未绑定（首次登录时自动补发邮件）。
    ticket, candidate = begin_pending_otp(student, "student", "register_bind")
    return jsonify(
        {
            "success": True,
            "message": "注册成功！请立即绑定动态验证码（OTP）",
            "otp_bind": pending_otp_bundle(ticket, candidate, student_id),
        }
    )


@auth_bp.post("/api/auth/otp/bind/confirm")
def confirm_otp_bind():
    """Confirm a pending OTP bind/reset: the new secret takes effect only when
    the returned 6-digit code proves the candidate secret was actually scanned."""
    data = request.get_json(silent=True) or {}
    ticket = data.get("ticket", "").strip()
    code = data.get("otp_code", "").strip()
    if not ticket or not code:
        return _json_error("请输入动态验证码")

    claims, error = decode_pending_otp(ticket)
    if claims is None:
        return _json_error(error, 401)

    user_type = claims.get("user_type", "")
    if user_type not in {"student", "admin"}:
        return _json_error("无效的绑定请求", 401)
    account = _load_account(user_type, claims.get("sub", ""))
    if account is None:
        return _json_error("账号不存在", 401)

    if not confirm_pending_otp(account, claims, code):
        return _json_error("验证码错误，请确认已用验证器扫描最新二维码后重试")

    try:
        set_totp_secret(account, claims["candidate_secret"])
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify({"success": True, "message": "动态验证码绑定成功"})


def _reset_rate_limited(key: str) -> bool:
    now = time.time()
    with _reset_lock:
        attempts = [item for item in _reset_attempts.get(key, []) if now - item < _RESET_WINDOW_SECONDS]
        if len(attempts) >= _RESET_MAX_ATTEMPTS:
            _reset_attempts[key] = attempts
            return True
        attempts.append(now)
        _reset_attempts[key] = attempts
    return False


@auth_bp.post("/api/student/forgot_password/send_code")
def send_forgot_password_code():
    """忘记密码第一步：向学号邮箱发送验证码（与注册同构）。"""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "").strip()
    generic_message = "如果学号存在，验证码邮件将发送到对应学生邮箱"

    if not student_id:
        return _json_error(generic_message)
    rate_key = f"forgot:{student_id}:{request.remote_addr or 'unknown'}"
    if _reset_rate_limited(rate_key):
        return _json_error("请求过于频繁，请稍后再试", 429)

    student = db.session.get(Student, student_id)
    if student is None:
        # Generic response avoids student-ID enumeration.
        return jsonify({"success": True, "message": generic_message})

    success, message = _send_email_code(student_id, student.name, "重置密码")
    if not success:
        return _json_error(message)
    return jsonify({"success": True, "message": message})


@auth_bp.post("/api/student/forgot_password")
def forgot_password():
    """忘记密码第二步：邮箱验证码 + 自设新密码，验证通过才重置。

    成功后返回一次性 OTP 绑定票据（与注册一致）：学生在弹窗中扫码并输入
    验证码确认后新 OTP 才生效；跳过则原有 OTP 保持不变。
    """
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "").strip()
    new_password = data.get("new_password", "")
    password_digest = data.get("password_hash", "").strip().lower()
    email_code = data.get("email_code", "").strip()

    if not student_id:
        return _json_error("请输入学号")
    if not (new_password or password_digest):
        return _json_error("请设置新密码")
    if new_password and len(new_password) < 6:
        return _json_error("新密码至少需要6位字符")
    if password_digest and not PASSWORD_DIGEST_PATTERN.fullmatch(password_digest):
        return _json_error("密码格式不正确")
    if not email_code:
        return _json_error("请输入邮箱验证码")

    student = db.session.get(Student, student_id)
    if student is None:
        return _json_error("学号不存在")

    code_error = _check_registration_code(student_id, email_code)
    if code_error:
        return _json_error(code_error)

    try:
        student.password_hash = hash_password_digest(
            password_digest or client_password_digest(new_password)
        )
        student.password_reset_required = False
        # 找回密码后：旧令牌与"免 OTP"信任记录全部作废
        student.token_version = (student.token_version or 0) + 1
        revoke_trusted_devices(student)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    ticket, candidate = begin_pending_otp(student, "student", "student_reset")
    return jsonify(
        {
            "success": True,
            "message": "密码已重置！可选择立即重新绑定动态验证码（OTP）",
            "otp_bind": pending_otp_bundle(ticket, candidate, student_id),
        }
    )
