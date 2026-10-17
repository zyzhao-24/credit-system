"""Student administration API."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from backend.auth.decorators import require_admin, require_system_admin
from backend.extensions import db
from backend.models import Student
from backend.services.exporters import csv_file_response
from backend.services.legacy_import import DATETIME_FORMAT
from backend.services.ranking import format_datetime
from backend.services.students import PHONE_PATTERN, create_student, delete_student_account
from backend.utils.passwords import client_password_digest, hash_password_digest


admin_students_bp = Blueprint("admin_students", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _apply_password(student: Student, password: str | None = None, password_hash: str | None = None) -> None:
    digest = password_hash or client_password_digest(password or "")
    student.password_hash = hash_password_digest(digest)
    student.password_reset_required = False


@admin_students_bp.route("/api/admin/students", methods=["GET", "POST", "PUT", "DELETE"])
@require_admin
def manage_students():
    identity = g.current_identity
    is_system_admin = identity.get("role") == "system_admin"

    if request.method == "GET":
        students = [
            {"student_id": student.student_id, "name": student.name}
            for student in Student.query.order_by(Student.student_id.asc()).all()
        ]
        return jsonify({"success": True, "students": students, "can_edit": is_system_admin})

    if not is_system_admin:
        return _error("仅系统管理员可以管理学生", 403)

    data = request.get_json(silent=True) or {}
    if request.method == "POST":
        student_id = data.get("student_id", "").strip()
        name = data.get("name", "").strip()
        password = data.get("password", "123456")
        password_digest = data.get("password_hash", "").strip().lower()

        if not student_id.isdigit():
            return _error("学号只能包含数字")
        if not name:
            return _error("姓名不能为空")
        if db.session.get(Student, student_id):
            return _error("学号已存在")

        try:
            create_student(
                student_id,
                name,
                password_digest or password,
                password_is_digest=bool(password_digest),
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return jsonify({"success": True, "message": "已添加学生"})

    if request.method == "PUT":
        student_id = data.get("student_id", "")
        student = db.session.get(Student, student_id)
        if student is None:
            return _error("学生不存在")
        if "name" in data:
            student.name = data["name"]
        if "password_hash" in data or "password" in data:
            _apply_password(student, data.get("password"), data.get("password_hash"))
        db.session.commit()
        return jsonify({"success": True})

    student_id = data.get("student_id", "")
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("学生不存在")
    deleted_responses = delete_student_account(student)
    db.session.commit()
    return jsonify(
        {"success": True, "message": f"已删除学生及其{deleted_responses}条报名记录"}
    )


@admin_students_bp.post("/api/admin/students/batch")
@require_system_admin
def batch_students():
    data = request.get_json(silent=True) or {}
    csv_data = data.get("csv_data", "")
    added = 0
    updated = 0
    errors: list[str] = []

    try:
        for line_number, raw_line in enumerate(csv_data.strip().splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 2:
                errors.append(f"第{line_number}行格式错误: {line}")
                continue
            student_id = parts[0].strip()
            name = parts[1].strip()
            explicit_password = parts[2].strip() if len(parts) > 2 else ""

            if not student_id.isdigit():
                errors.append(f"第{line_number}行学号必须是数字: {student_id}")
                continue
            if not name:
                errors.append(f"第{line_number}行姓名为空")
                continue

            student = db.session.get(Student, student_id)
            if student:
                student.name = name
                if explicit_password:
                    _apply_password(student, explicit_password)
                updated += 1
            else:
                create_student(student_id, name, explicit_password or "123456")
                added += 1
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return _error(f"解析失败: {exc}")

    return jsonify({"success": True, "added": added, "updated": updated, "errors": errors})


@admin_students_bp.get("/api/admin/students/export_csv")
@require_system_admin
def export_students_csv():
    rows = (
        (student.student_id, student.name, "")
        for student in Student.query.order_by(Student.student_id.asc()).all()
    )
    return csv_file_response("学生名单.csv", ["学号", "姓名", "密码"], rows)


@admin_students_bp.post("/api/admin/change_student_password")
@require_system_admin
def change_student_password():
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "")
    new_password = data.get("new_password", "")
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("学生不存在")
    if not new_password:
        return _error("新密码不能为空")
    _apply_password(student, new_password)
    db.session.commit()
    return jsonify({"success": True, "message": "密码修改成功"})


# ========== 学生报名信息（原注册问卷，已并入 students 表） ==========


def _info_payload(student: Student) -> dict:
    return {
        "student_id": student.student_id,
        "name": student.name,
        "phone": student.phone,
        "wechat": student.wechat,
        "suggestion": student.suggestion,
        "updated_at": student.info_updated_at.strftime(DATETIME_FORMAT)
        if student.info_updated_at
        else "",
    }


@admin_students_bp.get("/api/admin/students/info")
@require_system_admin
def list_student_infos():
    items = [
        _info_payload(student)
        for student in Student.query.order_by(Student.student_id.asc()).all()
    ]
    return jsonify({"success": True, "students": items, "total": len(items)})


@admin_students_bp.put("/api/admin/students/info")
@require_system_admin
def update_student_info():
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "").strip()
    phone = data.get("phone", "").strip()
    wechat = data.get("wechat", "").strip()
    suggestion = data.get("suggestion", "").strip()
    if phone and not PHONE_PATTERN.fullmatch(phone):
        return _error("手机号格式不正确")

    student = db.session.get(Student, student_id)
    if student is None:
        return _error("学生不存在")
    student.phone = phone
    student.wechat = wechat
    student.suggestion = suggestion
    student.info_updated_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True, "message": "更新成功"})


@admin_students_bp.get("/api/admin/students/info/export")
@require_system_admin
def export_student_infos():
    rows = (
        (
            student.student_id,
            student.name,
            student.phone,
            student.wechat,
            student.suggestion,
            format_datetime(student.info_updated_at),
        )
        for student in Student.query.order_by(Student.student_id.asc()).all()
    )
    filename = f"student_infos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_file_response(filename, ["学号", "姓名", "手机号", "微信号", "建议", "更新时间"], rows)
