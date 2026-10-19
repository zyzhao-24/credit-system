"""Activity, record, and credit-entry administration API."""

from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from backend.auth.decorators import require_admin
from backend.extensions import db
from backend.models import (
    Activity,
    ActivityQuestionnaire,
    Category,
    Entry,
    QuestionnaireResponse,
    Record,
    Student,
)
from backend.services.legacy_import import DATETIME_FORMAT
from backend.services.permissions import check_activity_edit_permission
from backend.services.ranking import response_payload


admin_activities_bp = Blueprint("admin_activities", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _number(value: Any):
    number = float(value)
    return int(number) if number.is_integer() else number


def _dt(value) -> str:
    return value.strftime(DATETIME_FORMAT) if value else ""


def _activity_payload(activity: Activity, identity: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "activity_id": activity.activity_id,
        "name": activity.name,
        "categories": activity.categories,
        "records_count": len(activity.records),
        "department": activity.department,
        "created_by": activity.created_by or "",
        "allowed_editors": activity.allowed_editors,
        "has_questionnaire": activity.has_questionnaire,
        "questionnaire_start": _dt(activity.questionnaire_start),
        "questionnaire_end": _dt(activity.questionnaire_end),
        "max_participants": activity.max_participants,
        "can_edit": check_activity_edit_permission(identity, activity.activity_id),
    }
    if activity.has_questionnaire:
        payload["current_participants"] = (
            QuestionnaireResponse.query.join(
                ActivityQuestionnaire,
                QuestionnaireResponse.questionnaire_id == ActivityQuestionnaire.questionnaire_id,
            )
            .filter(
                ActivityQuestionnaire.activity_id == activity.activity_id,
                QuestionnaireResponse.status == "active",
            )
            .count()
        )
    return payload


def _validate_categories(names: list[str]) -> bool:
    return bool(names) and all(db.session.get(Category, name) is not None for name in names)


def _entry_categories_error(record: Record, names: list[str]) -> str | None:
    """条目类别必须存在且属于记录的可行类别；返回错误消息或 None。"""
    if not _validate_categories(names):
        return "类别不存在或未选择"
    invalid = [name for name in names if name not in record.categories]
    if invalid:
        return f"条目类别必须属于记录类别（{'、'.join(invalid)} 不在该记录的类别中）"
    return None


def _record_or_error(record_id: str):
    record = db.session.get(Record, record_id)
    if record is None:
        return None, _error("记录不存在")
    if not check_activity_edit_permission(g.current_identity, record.activity_id):
        return None, _error("无权限编辑此活动", 403)
    return record, None


@admin_activities_bp.route("/api/admin/activities", methods=["GET", "POST", "PUT", "DELETE"])
@require_admin
def manage_activities():
    identity = g.current_identity

    if request.method == "GET":
        activities = [
            _activity_payload(activity, identity)
            for activity in Activity.query.order_by(Activity.position.asc()).all()
        ]
        return jsonify({"success": True, "activities": activities})

    data = request.get_json(silent=True) or {}
    if request.method == "POST":
        name = data.get("name", "").strip()
        department = data.get("department", "")
        if not name:
            return _error("活动名称不能为空")
        if Activity.query.filter_by(name=name).first():
            return _error("活动名称已存在")

        activity_id = str(uuid.uuid4())
        position = db.session.query(func.max(Activity.position)).scalar() or 0
        activity = Activity(
            activity_id=activity_id,
            name=name,
            department=department,
            created_by=identity.get("sub"),
            position=position + 1,
        )
        activity.allowed_editors = [identity.get("sub")]
        db.session.add(activity)
        db.session.commit()
        return jsonify({"success": True, "activity_id": activity_id})

    if request.method == "PUT":
        activity_id = data.get("activity_id", "")
        activity = db.session.get(Activity, activity_id)
        if activity is None:
            return _error("活动不存在")
        is_system_admin = identity.get("role") == "system_admin"

        if "department" in data or "allowed_editors" in data:
            if not is_system_admin:
                return _error("仅系统管理员可以修改活动权限", 403)
            if "department" in data:
                activity.department = data["department"]
            if "allowed_editors" in data:
                activity.allowed_editors = data["allowed_editors"]

        db.session.commit()
        return jsonify({"success": True})

    activity_id = data.get("activity_id", "")
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        return _error("活动不存在")
    if not check_activity_edit_permission(identity, activity_id):
        return _error("无权限删除此活动", 403)
    db.session.delete(activity)
    db.session.commit()
    return jsonify({"success": True})


@admin_activities_bp.route("/api/admin/records", methods=["POST", "PUT", "DELETE"])
@require_admin
def manage_records():
    data = request.get_json(silent=True) or {}

    if request.method == "POST":
        activity_id = data.get("activity_id", "")
        record_name = data.get("record_name", "").strip()
        categories = data.get("categories", [])
        activity = db.session.get(Activity, activity_id)
        if activity is None:
            return _error("活动不存在")
        if not check_activity_edit_permission(g.current_identity, activity_id):
            return _error("无权限编辑此活动", 403)
        if not record_name:
            return _error("记录名称不能为空")
        if not _validate_categories(categories):
            return _error("请至少选择一个有效类别")
        record_id = str(uuid.uuid4())
        record = Record(record_id=record_id, record_name=record_name, position=len(activity.records))
        record.categories = categories
        activity.records.append(record)
        db.session.commit()
        return jsonify({"success": True, "record_id": record_id})

    if request.method == "PUT":
        record, error = _record_or_error(data.get("record_id", ""))
        if error:
            return error
        if "record_name" in data:
            new_name = data.get("record_name", "")
            if not new_name or not new_name.strip():
                return _error("记录名称不能为空")
            record.record_name = new_name.strip()
        if "categories" in data:
            categories = data["categories"]
            if not _validate_categories(categories):
                return _error("请至少选择一个有效类别")
            # 缩减类别时，仍在使用被移除类别的条目会失效，拒绝并要求先调整条目
            removed = set(record.categories) - set(categories)
            if removed:
                blocking = sorted(
                    {name for entry in record.entries for name in entry.categories if name in removed}
                )
                if blocking:
                    return _error(
                        f"仍有条目使用类别：{'、'.join(blocking)}，请先调整这些条目后再缩减记录类别"
                    )
            record.categories = categories
        db.session.commit()
        return jsonify({"success": True})

    record, error = _record_or_error(data.get("record_id", ""))
    if error:
        return error
    db.session.delete(record)
    db.session.commit()
    return jsonify({"success": True})


@admin_activities_bp.route("/api/admin/entries", methods=["POST", "PUT", "DELETE"])
@require_admin
def manage_entries():
    data = request.get_json(silent=True) or {}
    record, error = _record_or_error(data.get("record_id", ""))
    if error:
        return error

    if request.method == "POST":
        student_id = data.get("student_id", "").strip()
        if student_id and not student_id.isdigit():
            return _error("学号只能包含数字")
        categories = data.get("categories", [])
        category_error = _entry_categories_error(record, categories)
        if category_error:
            return _error(category_error)
        entry = Entry(
            student_id=student_id,
            credits=float(data.get("credits", 0)),
            position=len(record.entries),
        )
        entry.categories = categories
        record.entries.append(entry)
        db.session.commit()
        return jsonify({"success": True, "entry_id": entry.entry_id})

    if request.method == "PUT":
        entry = None
        if data.get("entry_id") is not None:
            entry = db.session.get(Entry, int(data["entry_id"]))
            if entry is None or entry.record_id != record.record_id:
                entry = None
        else:
            student_id = data.get("student_id")
            entry = next((item for item in record.entries if item.student_id == student_id), None)
        if entry is None:
            return _error("条目不存在")
        if "credits" in data:
            entry.credits = float(data["credits"])
        if "categories" in data:
            category_error = _entry_categories_error(record, data["categories"])
            if category_error:
                return _error(category_error)
            entry.categories = data["categories"]
        db.session.commit()
        return jsonify({"success": True})

    if data.get("entry_id") is not None:
        entry = db.session.get(Entry, int(data["entry_id"]))
        if entry is None or entry.record_id != record.record_id:
            return _error("条目不存在")
        db.session.delete(entry)
        deleted = 1
    else:
        student_id = data.get("student_id")
        matches = [entry for entry in record.entries if entry.student_id == student_id]
        deleted = len(matches)
        for entry in matches:
            db.session.delete(entry)
    db.session.commit()
    return jsonify({"success": True, "deleted": deleted})


@admin_activities_bp.get("/api/admin/activities/<activity_id>/records")
@require_admin
def get_activity_records(activity_id: str):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        return _error("活动不存在")
    records = [
        {
            "record_id": record.record_id,
            "record_name": record.record_name,
            "entries_count": len(record.entries),
            "categories": record.categories,
        }
        for record in activity.records
    ]
    return jsonify({"success": True, "records": records})


@admin_activities_bp.get("/api/admin/records/<record_id>")
@require_admin
def get_record_detail(record_id: str):
    record = db.session.get(Record, record_id)
    if record is None:
        return _error("记录不存在")
    activity = record.activity
    entries = []
    for entry in record.entries:
        student = db.session.get(Student, entry.student_id)
        entries.append(
            {
                "entry_id": entry.entry_id,
                "student_id": entry.student_id,
                "student_name": student.name if student else "(学生不存在)",
                "credits": _number(entry.credits),
                "categories": entry.categories,
                "student_exists": student is not None,
            }
        )
    return jsonify(
        {
            "success": True,
            "record": {
                "record_id": record.record_id,
                "record_name": record.record_name,
                "activity_id": record.activity_id,
                "activity_name": activity.name if activity else "未知",
                "categories": record.categories,
                "activity_categories": activity.categories if activity else [],
                "entries": entries,
            },
        }
    )


@admin_activities_bp.get("/api/admin/records/<record_id>/checked_in_missing")
@require_admin
def checked_in_missing(record_id: str):
    """该记录下"已签到（有效）但还没有条目"的学生，供录入学分时对照/快速添加。

    签到有效性规则与问卷一致：名额内签到即有效；候补签到须管理员确认或转正。
    """
    record = db.session.get(Record, record_id)
    if record is None:
        return _error("记录不存在")
    if not check_activity_edit_permission(g.current_identity, record.activity_id):
        return _error("无权限", 403)
    template = (
        ActivityQuestionnaire.query.filter_by(activity_id=record.activity_id, status="active")
        .order_by(ActivityQuestionnaire.created_time.desc())
        .first()
    )
    students = []
    if template is not None:
        entered = {entry.student_id for entry in record.entries}
        responses = (
            QuestionnaireResponse.query.filter_by(
                questionnaire_id=template.questionnaire_id, status="active"
            )
            .order_by(QuestionnaireResponse.checked_in_at.asc())
            .all()
        )
        for response in responses:
            if (
                not response.checked_in_at
                or response.absent
                or response.student_id in entered
            ):
                continue
            payload = response_payload(response, template)
            if payload["checkin_state"] != "valid":
                continue
            students.append(
                {
                    "student_id": response.student_id,
                    "student_name": response.student_name,
                    "intended_category": response.intended_category,
                    "checked_in_at": payload["checked_in_at"],
                }
            )
    return jsonify({"success": True, "students": students})


@admin_activities_bp.post("/api/admin/entries/batch")
@require_admin
def batch_entries():
    data = request.get_json(silent=True) or {}
    record, error = _record_or_error(data.get("record_id", ""))
    if error:
        return error
    categories = data.get("categories", [])
    category_error = _entry_categories_error(record, categories)
    if category_error:
        return _error(category_error)
    default_credits = data.get("default_credits", 0)

    added = updated = ignored = 0
    errors: list[str] = []
    for line_number, raw_line in enumerate(data.get("entries_text", "").strip().splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(",")
        identifier = parts[0].strip()
        if len(parts) >= 2:
            try:
                credits = float(parts[1].strip())
            except ValueError:
                errors.append(f"第{line_number}行学分格式错误: {parts[1]}")
                continue
        else:
            credits = default_credits

        if identifier.isdigit():
            student_ids = [identifier]
        else:
            student_ids = [
                student.student_id for student in Student.query.filter_by(name=identifier).all()
            ]
            if not student_ids:
                ignored += 1
                continue

        for student_id in student_ids:
            entry = next((item for item in record.entries if item.student_id == student_id), None)
            if entry:
                entry.credits = float(credits)
                entry.categories = categories
                updated += 1
            else:
                entry = Entry(
                    student_id=student_id,
                    credits=float(credits),
                    position=len(record.entries),
                )
                entry.categories = categories
                record.entries.append(entry)
                added += 1

    db.session.commit()
    return jsonify({"success": True, "added": added, "updated": updated, "ignored": ignored, "errors": errors})


@admin_activities_bp.post("/api/admin/entries/batch_update")
@require_admin
def batch_update_entries():
    data = request.get_json(silent=True) or {}
    record, error = _record_or_error(data.get("record_id", ""))
    if error:
        return error
    student_ids = data.get("student_ids", [])
    updated = 0
    for entry in record.entries:
        if entry.student_id in student_ids:
            if data.get("credits") is not None:
                entry.credits = float(data["credits"])
            if data.get("categories") is not None:
                category_error = _entry_categories_error(record, data["categories"])
                if category_error:
                    return _error(category_error)
                entry.categories = data["categories"]
            updated += 1
    db.session.commit()
    return jsonify({"success": True, "updated": updated})


@admin_activities_bp.post("/api/admin/entries/batch_delete")
@require_admin
def batch_delete_entries():
    data = request.get_json(silent=True) or {}
    record, error = _record_or_error(data.get("record_id", ""))
    if error:
        return error
    student_ids = set(data.get("student_ids", []))
    matches = [entry for entry in record.entries if entry.student_id in student_ids]
    for entry in matches:
        db.session.delete(entry)
    db.session.commit()
    return jsonify({"success": True, "deleted": len(matches)})
