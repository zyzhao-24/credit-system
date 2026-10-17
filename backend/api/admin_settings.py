"""System settings and administrator account API."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from backend.auth.decorators import require_admin, require_system_admin
from backend.extensions import db
from backend.models import Activity, ActivityAllowedEditor, Admin, Category, Department, Setting
from backend.services.otp_service import bind_new_totp, has_totp
from backend.utils.otp import qr_png_data_uri
from backend.utils.passwords import client_password_digest, hash_password_digest


admin_settings_bp = Blueprint("admin_settings", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _number(value):
    number = float(value)
    return int(number) if number.is_integer() else number


@admin_settings_bp.route("/api/admin/categories", methods=["GET", "POST", "PUT", "DELETE"])
@require_admin
def manage_categories():
    if request.method == "GET":
        categories = [
            {"name": category.name, "required_credits": _number(category.required_credits)}
            for category in Category.query.order_by(Category.position.asc()).all()
        ]
        return jsonify({"success": True, "categories": categories})

    if g.current_identity.get("role") != "system_admin":
        return _error("仅系统管理员可以管理类别", 403)

    data = request.get_json(silent=True) or {}
    if request.method == "POST":
        name = data.get("name", "").strip()
        if not name:
            return _error("类别名称不能为空")
        if db.session.get(Category, name):
            return _error("类别已存在")
        position = db.session.query(func.max(Category.position)).scalar() or 0
        db.session.add(
            Category(
                name=name,
                required_credits=float(data.get("required_credits", 0)),
                position=position + 1,
            )
        )
        db.session.commit()
        return jsonify({"success": True})

    if request.method == "PUT":
        name = data.get("name", "")
        category = db.session.get(Category, name)
        if category is None:
            return _error("类别不存在")
        if "required_credits" in data:
            category.required_credits = float(data["required_credits"])
        db.session.commit()
        return jsonify({"success": True})

    name = data.get("name", "")
    category = db.session.get(Category, name)
    if category is None:
        return _error("类别不存在")
    try:
        db.session.delete(category)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error("该类别仍被活动或积分条目使用，无法删除")
    return jsonify({"success": True})


@admin_settings_bp.route("/api/admin/total_credits", methods=["GET", "POST"])
@require_system_admin
def manage_total_credits():
    if request.method == "GET":
        setting = db.session.get(Setting, "total_required_credits")
        return jsonify(
            {"success": True, "total_required_credits": _number(setting.value) if setting else 0}
        )

    data = request.get_json(silent=True) or {}
    setting = db.session.get(Setting, "total_required_credits")
    if setting is None:
        setting = Setting(key="total_required_credits")
        db.session.add(setting)
    setting.value = str(data.get("total_required_credits", 0))
    db.session.commit()
    return jsonify({"success": True})


@admin_settings_bp.route("/api/admin/departments", methods=["GET", "POST", "DELETE"])
@require_admin
def manage_departments():
    if request.method == "GET":
        departments = [
            department.name
            for department in Department.query.order_by(Department.position.asc()).all()
        ]
        return jsonify({"success": True, "departments": departments})

    if g.current_identity.get("role") != "system_admin":
        action = "添加" if request.method == "POST" else "删除"
        return _error(f"仅系统管理员可以{action}部门", 403)

    data = request.get_json(silent=True) or {}
    name = data.get("department", "").strip()
    if request.method == "POST":
        if not name:
            return _error("部门名称不能为空")
        if Department.query.filter_by(name=name).first():
            return _error("部门已存在")
        position = db.session.query(func.max(Department.position)).scalar() or 0
        db.session.add(Department(name=name, position=position + 1))
        db.session.commit()
        return jsonify({"success": True})

    department = Department.query.filter_by(name=name).first()
    if department is None:
        return _error("部门不存在")
    db.session.delete(department)
    db.session.commit()
    return jsonify({"success": True})


SYSTEM_ADMIN_ID = "system"


@admin_settings_bp.route("/api/admin/admins", methods=["GET", "POST", "PUT", "DELETE"])
@require_system_admin
def manage_admins():
    if request.method == "GET":
        admins = [
            {
                "admin_id": admin.admin_id,
                "role": admin.role,
                "department": admin.department,
                "has_otp": has_totp(admin),
            }
            for admin in Admin.query.order_by(Admin.admin_id.asc()).all()
        ]
        return jsonify({"success": True, "admins": admins})

    data = request.get_json(silent=True) or {}
    current_admin_id = g.current_identity.get("sub")

    if request.method == "POST":
        admin_id = data.get("admin_id", "").strip()
        password = data.get("password", "admin123")
        role = data.get("role", "admin")
        department = data.get("department", "")
        if not admin_id:
            return _error("账号不能为空")
        if admin_id == SYSTEM_ADMIN_ID:
            return _error("system 为内置系统管理员账号，不能通过接口创建")
        # 系统管理员固定只有内置 system 账号，接口只能创建普通管理员
        if role != "admin":
            return _error("只能通过接口创建普通管理员（系统管理员为内置 system 账号）")
        if db.session.get(Admin, admin_id):
            return _error("账号已存在")
        admin = Admin(
            admin_id=admin_id,
            password_hash=hash_password_digest(client_password_digest(password)),
            role=role,
            department=department,
        )
        db.session.add(admin)
        # 创建时必须绑定 OTP：密钥随响应一次性返回
        secret, uri = bind_new_totp(admin)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "otp_secret": secret,
                "otp_uri": uri,
                "otp_qr": qr_png_data_uri(uri),
            }
        )

    if request.method == "PUT":
        admin_id = data.get("admin_id", "")
        admin = db.session.get(Admin, admin_id)
        if admin is None:
            return _error("管理员不存在")
        if admin_id == SYSTEM_ADMIN_ID:
            return _error("system 账号的密码与 OTP 只能通过 manage.py 命令修改")
        if admin_id == current_admin_id and "department" in data:
            return _error("不能修改自己的部门")
        if "password" in data:
            admin.password_hash = hash_password_digest(client_password_digest(data["password"]))
        if "role" in data:
            # 不允许通过接口提升为系统管理员（固定只有内置 system）
            if data["role"] != "admin":
                return _error("不能将账号设为系统管理员（系统管理员为内置 system 账号）")
            admin.role = data["role"]
        if "department" in data:
            admin.department = data["department"]
        db.session.commit()
        return jsonify({"success": True})

    admin_id = data.get("admin_id", "")
    admin = db.session.get(Admin, admin_id)
    if admin is None:
        return _error("管理员不存在")
    if admin_id == SYSTEM_ADMIN_ID:
        return _error("system 为内置系统管理员账号，不允许删除")
    if admin_id == current_admin_id:
        return _error("不能删除自己的账号")
    if admin.role == "system_admin":
        return _error("不能删除系统管理员")
    ActivityAllowedEditor.query.filter_by(admin_id=admin_id).delete()
    Activity.query.filter_by(created_by=admin_id).update({"created_by": None})
    db.session.delete(admin)
    db.session.commit()
    return jsonify({"success": True})


@admin_settings_bp.post("/api/admin/admins/reset_otp")
@require_system_admin
def reset_admin_otp():
    """重新生成普通管理员的 OTP（system 账号只能走 manage.py）。"""
    data = request.get_json(silent=True) or {}
    admin_id = data.get("admin_id", "").strip()
    if admin_id == SYSTEM_ADMIN_ID:
        return _error("system 账号的 OTP 只能通过 manage.py 重置")
    admin = db.session.get(Admin, admin_id)
    if admin is None:
        return _error("管理员不存在")
    secret, uri = bind_new_totp(admin)
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "otp_secret": secret,
            "otp_uri": uri,
            "otp_qr": qr_png_data_uri(uri),
        }
    )
