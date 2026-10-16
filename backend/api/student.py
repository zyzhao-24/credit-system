"""Student-facing base API."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from backend.auth.decorators import require_auth, require_student
from backend.extensions import db
from backend.models import Activity, Category, RegistrationQuestionnaire, Student
from backend.services.credits import calculate_student_credits
from backend.services.legacy_import import DATETIME_FORMAT
from backend.services.students import PHONE_PATTERN
from backend.utils.passwords import client_password_digest, hash_password_digest, verify_password_digest


student_bp = Blueprint("student", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _number(value):
    number = float(value)
    return int(number) if number.is_integer() else number


@student_bp.get("/api/student/my_credits")
@require_student
def my_credits():
    student_id = g.current_identity.get("sub")
    result = calculate_student_credits(student_id)
    result.update(
        {
            "student_id": student_id,
            "student_name": g.current_identity.get("name"),
            "success": True,
        }
    )
    return jsonify(result)


@student_bp.post("/api/student/change_password")
@require_student
def change_password():
    data = request.get_json(silent=True) or {}
    old_digest = data.get("old_password_hash", "").strip().lower()
    new_password = data.get("new_password", "")
    new_digest = data.get("new_password_hash", "").strip().lower()

    student = db.session.get(Student, g.current_identity.get("sub"))
    if student is None:
        return _error("学生不存在")
    if not verify_password_digest(student.password_hash, old_digest):
        return _error("原密码错误")
    if not new_password and not new_digest:
        return _error("新密码不能为空")

    student.password_hash = hash_password_digest(new_digest or client_password_digest(new_password))
    student.password_reset_required = False
    db.session.commit()
    return jsonify({"success": True, "message": "密码修改成功"})


@student_bp.get("/api/student/activities")
@require_student
def student_activities():
    category_activities: dict[str, list[dict[str, str]]] = {}
    no_category_activities: list[dict[str, str]] = []
    for activity in Activity.query.order_by(Activity.position.asc()).all():
        if not activity.categories:
            no_category_activities.append(
                {"activity_id": activity.activity_id, "activity_name": activity.name}
            )
            continue
        for category in activity.categories:
            category_activities.setdefault(category, []).append(
                {"activity_id": activity.activity_id, "activity_name": activity.name}
            )
    return jsonify(
        {
            "success": True,
            "category_activities": category_activities,
            "no_category_activities": no_category_activities,
        }
    )


@student_bp.get("/api/student/categories")
@require_student
def student_categories():
    categories = [
        {
            "category_id": category.name,
            "name": category.name,
            "required_credits": _number(category.required_credits),
        }
        for category in Category.query.order_by(Category.position.asc()).all()
    ]
    return jsonify({"success": True, "categories": categories})


@student_bp.get("/api/student/registration_questionnaire")
@require_student
def get_registration_questionnaire():
    questionnaire = RegistrationQuestionnaire.query.filter_by(
        student_id=g.current_identity.get("sub")
    ).first()
    if questionnaire is None:
        return _error("未找到注册问卷")
    return jsonify(
        {
            "success": True,
            "questionnaire": {
                "questionnaire_id": questionnaire.questionnaire_id,
                "student_id": questionnaire.student_id,
                "name": questionnaire.name,
                "phone": questionnaire.phone,
                "wechat": questionnaire.wechat,
                "suggestion": questionnaire.suggestion,
                "submit_time": questionnaire.submit_time.strftime(DATETIME_FORMAT),
            },
        }
    )


@student_bp.put("/api/student/registration_questionnaire")
@require_student
def update_registration_questionnaire():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    wechat = data.get("wechat", "").strip()
    suggestion = data.get("suggestion", "").strip()
    if phone and not PHONE_PATTERN.fullmatch(phone):
        return _error("手机号格式不正确")

    questionnaire = RegistrationQuestionnaire.query.filter_by(
        student_id=g.current_identity.get("sub")
    ).first()
    if questionnaire is None:
        return _error("未找到注册问卷")
    questionnaire.phone = phone
    questionnaire.wechat = wechat
    questionnaire.suggestion = suggestion
    db.session.commit()
    return jsonify({"success": True, "message": "更新成功"})


@student_bp.get("/api/student/activity/<activity_id>/categories")
@require_auth
def activity_categories(activity_id: str):
    if g.current_identity.get("user_type") not in {"student", "admin"}:
        return _error("无权限", 403)
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        return _error("活动不存在")
    return jsonify({"success": True, "categories": activity.categories})
