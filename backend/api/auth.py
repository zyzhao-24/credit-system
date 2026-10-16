"""Authentication and public student registration API."""

from __future__ import annotations

import re
import secrets
import threading
import time
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from backend.auth.decorators import require_auth, require_admin
from backend.auth.jwt import issue_token
from backend.extensions import db
from backend.models import Admin, EmailConfig, RegistrationQuestionnaire, Student
from backend.services.emailer import send_email
from backend.services.students import (
    PHONE_PATTERN,
    create_student,
    ensure_all_registration_questionnaires,
    ensure_registration_questionnaire,
)
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


def _json_error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _resolve_user_type(username: str, requested: str) -> str | None:
    if requested in {"student", "admin"}:
        return requested
    if not requested:
        return "student" if username.isdigit() else "admin"
    return None


def _issue_for_user(user_type: str, username: str, password_digest: str):
    if not PASSWORD_DIGEST_PATTERN.fullmatch(password_digest):
        return None

    if user_type == "student":
        student = db.session.get(Student, username)
        if student is None or not verify_password_digest(student.password_hash, password_digest):
            return None
        ensure_registration_questionnaire(student)
        db.session.commit()
        return {
            "id": student.student_id,
            "user_type": "student",
            "name": student.name,
            "role": "",
            "department": "",
        }

    admin = db.session.get(Admin, username)
    if admin is None or not verify_password_digest(admin.password_hash, password_digest):
        return None
    if admin.role == "system_admin":
        ensure_all_registration_questionnaires()
        db.session.commit()
    return {
        "id": admin.admin_id,
        "user_type": "admin",
        "name": admin.admin_id,
        "role": admin.role,
        "department": admin.department,
    }


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
    }


@auth_bp.post("/api/auth/token")
def oauth2_token():
    """OAuth2 Password-compatible token endpoint.

    The password field carries the client-side SHA-256 digest for compatibility
    with the legacy UI. It is verified again using the salted PBKDF2 hash.
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

    try:
        identity = _issue_for_user(user_type, username, password_digest)
    except Exception:
        db.session.rollback()
        raise
    if identity is None:
        return jsonify({"detail": "账号或密码错误"}), 401
    return jsonify(_token_payload(identity))


def _legacy_login(user_type: str):
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password_digest = data.get("password_hash", "").strip().lower()
    identity = _issue_for_user(user_type, username, password_digest)
    if identity is None:
        return _json_error("学号或密码错误" if user_type == "student" else "账号或密码错误")
    return jsonify({"success": True, **_token_payload(identity)})


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
def auth_logout():
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

    try:
        student = create_student(
            student_id,
            name,
            password_digest or client_password_digest(password),
            password_is_digest=True,
        )
        questionnaire = RegistrationQuestionnaire.query.filter_by(student_id=student.student_id).one()
        questionnaire.phone = phone
        questionnaire.wechat = wechat
        questionnaire.suggestion = suggestion
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify({"success": True, "message": "注册成功！请使用学号和密码登录"})


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


@auth_bp.post("/api/student/forgot_password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "").strip()
    generic_message = "如果学号存在，重置密码邮件将发送到对应学生邮箱"

    if not student_id:
        return _json_error(generic_message)
    rate_key = f"{student_id}:{request.remote_addr or 'unknown'}"
    if _reset_rate_limited(rate_key):
        return _json_error("请求过于频繁，请稍后再试", 429)

    student = db.session.get(Student, student_id)
    if student is None:
        # Generic response avoids student-ID enumeration.
        return jsonify({"success": True, "message": generic_message})
    if student.password_reset_required:
        return jsonify(
            {
                "success": False,
                "message": "您已申请过密码重置，新密码已发送到您的邮箱。\n请查收邮件并使用新密码登录。\n如未收到邮件，请联系管理员。",
                "already_requested": True,
            }
        )

    config = db.session.get(EmailConfig, 1)
    if not config or not config.service_email or not config.student_email_suffix:
        return _json_error("系统邮箱未配置，请联系管理员")

    new_password = secrets.token_urlsafe(8)[:8]
    student_email = f"{student_id}{config.student_email_suffix}"
    body = f"""
您好，{student.name} 同学：

您的团校积分系统密码已重置。

学号：{student_id}
新密码：{new_password}

请使用新密码登录系统，并及时修改密码。

如非本人操作，请立即联系管理员。

---
团校积分系统
    """
    success, message = send_email(student_email, "团校积分系统 - 密码重置", body)
    if not success:
        return _json_error(message)

    student.password_hash = hash_password_digest(client_password_digest(new_password))
    student.password_reset_required = True
    db.session.commit()
    return jsonify({"success": True, "message": f"新密码已发送至 {student_email}，请查收邮件"})
