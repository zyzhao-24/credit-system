"""Questionnaire administration API."""

from __future__ import annotations

import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth.decorators import require_admin, require_system_admin
from backend.extensions import db
from backend.models import (
    Activity,
    ActivityQuestionnaire,
    QuestionnaireResponse,
    RegistrationQuestionnaire,
)
from backend.services.exporters import csv_file_response
from backend.services.questionnaires import normalize_custom_questions, validate_template_window
from backend.services.ranking import format_datetime, response_payload, response_status
from backend.services.students import PHONE_PATTERN


admin_questionnaires_bp = Blueprint("admin_questionnaires", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _activity_name(activity_id: str) -> str:
    activity = db.session.get(Activity, activity_id)
    return activity.name if activity else "未知活动"


def _registration_payload(item: RegistrationQuestionnaire) -> dict:
    return {
        "questionnaire_id": item.questionnaire_id,
        "student_id": item.student_id,
        "name": item.name,
        "phone": item.phone,
        "wechat": item.wechat,
        "suggestion": item.suggestion,
        "submit_time": format_datetime(item.submit_time),
    }


def _template_payload(item: ActivityQuestionnaire) -> dict:
    response_count = QuestionnaireResponse.query.filter_by(
        questionnaire_id=item.questionnaire_id,
        status="active",
    ).count()
    return {
        "questionnaire_id": item.questionnaire_id,
        "questionnaire_type": "activity_template",
        "title": item.title,
        "activity_name": _activity_name(item.activity_id),
        "activity_id": item.activity_id,
        "start_time": format_datetime(item.start_time),
        "end_time": format_datetime(item.end_time),
        "max_participants": item.max_participants,
        "response_count": response_count,
        "status": item.status,
        "created_time": format_datetime(item.created_time),
        "is_ended": datetime.now() > item.end_time,
        "has_category_question": item.has_category_question,
        "custom_questions": item.custom_questions or [],
    }


def _sync_activity_questionnaire_fields(activity_id: str) -> None:
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        return
    template = (
        ActivityQuestionnaire.query.filter_by(activity_id=activity_id, status="active")
        .order_by(ActivityQuestionnaire.created_time.desc())
        .first()
    )
    if template is None:
        activity.has_questionnaire = False
        activity.questionnaire_start = None
        activity.questionnaire_end = None
        activity.max_participants = 0
    else:
        activity.has_questionnaire = True
        activity.questionnaire_start = template.start_time
        activity.questionnaire_end = template.end_time
        activity.max_participants = template.max_participants


@admin_questionnaires_bp.get("/api/admin/questionnaires/all")
@require_system_admin
def all_questionnaires():
    questionnaires = []
    for item in RegistrationQuestionnaire.query.all():
        payload = _registration_payload(item)
        payload["questionnaire_type"] = "registration"
        questionnaires.append(payload)
    questionnaires.extend(
        _template_payload(item) for item in ActivityQuestionnaire.query.all()
    )
    questionnaires.sort(
        key=lambda item: item.get("submit_time") or item.get("created_time", ""),
        reverse=True,
    )
    return jsonify({"success": True, "questionnaires": questionnaires, "total": len(questionnaires)})


@admin_questionnaires_bp.put("/api/admin/questionnaire/update")
@require_system_admin
def update_questionnaire():
    data = request.get_json(silent=True) or {}
    questionnaire_id = data.get("questionnaire_id", "")
    phone = data.get("phone", "").strip()
    wechat = data.get("wechat", "").strip()
    if phone and not PHONE_PATTERN.fullmatch(phone):
        return _error("手机号格式不正确")

    registration = db.session.get(RegistrationQuestionnaire, questionnaire_id)
    if registration:
        registration.phone = phone
        registration.wechat = wechat
        registration.suggestion = data.get("suggestion", "").strip()
        db.session.commit()
        return jsonify({"success": True, "message": "更新成功"})

    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template:
        status = data.get("status", template.status)
        if status not in {"active", "closed"}:
            return _error("问卷状态不正确")
        template.status = status
        db.session.commit()
        return jsonify({"success": True, "message": "更新成功"})
    return _error("问卷不存在")


@admin_questionnaires_bp.delete("/api/admin/questionnaire/<questionnaire_id>")
@require_system_admin
def delete_questionnaire(questionnaire_id: str):
    registration = db.session.get(RegistrationQuestionnaire, questionnaire_id)
    if registration:
        db.session.delete(registration)
        db.session.commit()
        return jsonify({"success": True, "message": "删除成功"})
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template:
        activity_id = template.activity_id
        db.session.delete(template)
        db.session.flush()
        _sync_activity_questionnaire_fields(activity_id)
        db.session.commit()
        return jsonify({"success": True, "message": "删除成功"})
    return _error("问卷不存在")


@admin_questionnaires_bp.post("/api/admin/questionnaire/create_template")
@require_system_admin
def create_template():
    data = request.get_json(silent=True) or {}
    activity_id = data.get("activity_id", "").strip()
    title = data.get("title", "").strip()
    if db.session.get(Activity, activity_id) is None:
        return _error("活动不存在")
    if not title:
        return _error("请输入问卷标题")
    try:
        max_participants = int(data.get("max_participants", 0))
    except (TypeError, ValueError):
        return _error("最大人数必须是数字")
    start, end, error = validate_template_window(
        data.get("start_time", "").strip(),
        data.get("end_time", "").strip(),
    )
    if error:
        return _error(error)
    if ActivityQuestionnaire.query.filter_by(activity_id=activity_id, status="active").first():
        return _error("该活动已存在问卷")
    questions, error = normalize_custom_questions(data.get("custom_questions", []))
    if error:
        return _error(error)

    template = ActivityQuestionnaire(
        questionnaire_id=str(uuid.uuid4()),
        activity_id=activity_id,
        title=title,
        start_time=start,
        end_time=end,
        max_participants=max_participants,
        has_category_question=bool(data.get("has_category_question", True)),
        custom_questions=questions,
        created_time=datetime.now(),
        status="active",
    )
    db.session.add(template)
    db.session.flush()
    _sync_activity_questionnaire_fields(activity_id)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("该活动已存在问卷")
    return jsonify({"success": True, "message": "创建成功", "questionnaire_id": template.questionnaire_id})


@admin_questionnaires_bp.put("/api/admin/questionnaire/template/<questionnaire_id>")
@require_system_admin
def update_template(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return _error("请输入问卷标题")
    try:
        max_participants = int(data.get("max_participants", 0))
    except (TypeError, ValueError):
        return _error("最大人数必须是数字")
    start, end, error = validate_template_window(
        data.get("start_time", "").strip(),
        data.get("end_time", "").strip(),
    )
    if error:
        return _error(error)
    questions, error = normalize_custom_questions(data.get("custom_questions", []), preserve_ids=True)
    if error:
        return _error(error)

    template.title = title
    template.start_time = start
    template.end_time = end
    template.max_participants = max_participants
    template.has_category_question = bool(data.get("has_category_question", template.has_category_question))
    template.custom_questions = questions
    _sync_activity_questionnaire_fields(template.activity_id)
    db.session.commit()
    return jsonify({"success": True, "message": "更新成功"})


@admin_questionnaires_bp.delete("/api/admin/questionnaire/template/<questionnaire_id>")
@require_system_admin
def delete_template(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    activity_id = template.activity_id
    db.session.delete(template)
    db.session.flush()
    _sync_activity_questionnaire_fields(activity_id)
    db.session.commit()
    return jsonify({"success": True, "message": "删除成功"})


@admin_questionnaires_bp.get("/api/admin/questionnaire/responses/<questionnaire_id>")
@require_admin
def questionnaire_responses(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    responses = [
        response_payload(response, template)
        for response in QuestionnaireResponse.query.filter_by(questionnaire_id=questionnaire_id).all()
    ]
    responses.sort(key=lambda item: (item["status"] != "active", item["submit_time"]))
    return jsonify({"success": True, "responses": responses})


@admin_questionnaires_bp.get("/api/admin/questionnaire/responses/<questionnaire_id>/export")
@require_admin
def export_responses(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    rows = []
    for response in QuestionnaireResponse.query.filter_by(questionnaire_id=questionnaire_id).all():
        payload = response_payload(response, template)
        status = response_status(response, template)
        if response.status == "cancelled":
            status_text = "已取消"
        elif status["is_ended"]:
            status_text = "已入选" if status["is_selected"] else "未入选"
        else:
            status_text = "候补" if status["is_waitlist"] else "已报名"
        rows.append(
            (
                payload["rank"] if payload["rank"] > 0 else "-",
                response.student_id,
                response.student_name,
                response.phone,
                response.wechat,
                response.intended_category,
                payload["submit_time"],
                status_text,
            )
        )
    rows.sort(key=lambda row: (row[7] == "已取消", row[6]))
    safe_title = template.title.replace(",", "_").replace("\n", "_").replace("\r", "_")
    return csv_file_response(
        f"{safe_title}_填写记录.csv",
        ["排名", "学号", "姓名", "手机号", "微信号", "意向学分类别", "提交时间", "状态"],
        rows,
    )


@admin_questionnaires_bp.put("/api/admin/questionnaire/response/<response_id>")
@require_system_admin
def update_response(response_id: str):
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    if phone:
        if not PHONE_PATTERN.fullmatch(phone):
            return _error("手机号格式不正确")
        response.phone = phone
    if data.get("wechat"):
        response.wechat = data["wechat"].strip()
    if data.get("intended_category"):
        response.intended_category = data["intended_category"].strip()
    db.session.commit()
    return jsonify({"success": True, "message": "修改成功"})


@admin_questionnaires_bp.delete("/api/admin/questionnaire/response/<response_id>")
@require_system_admin
def delete_response(response_id: str):
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    db.session.delete(response)
    db.session.commit()
    return jsonify({"success": True, "message": "删除成功"})


@admin_questionnaires_bp.get("/api/admin/questionnaires/export")
@require_system_admin
def export_all_questionnaires():
    type_filter = request.args.get("type", "")
    rows = []
    if not type_filter or type_filter == "registration":
        rows.extend(
            ("注册问卷", item.student_id, item.name, item.phone, item.wechat, item.suggestion or "", format_datetime(item.submit_time))
            for item in RegistrationQuestionnaire.query.all()
        )
    if not type_filter or type_filter == "activity":
        for response in QuestionnaireResponse.query.all():
            template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
            if not template:
                continue
            status_text = "已报名" if response.status == "active" else "已取消"
            remark = f"{_activity_name(template.activity_id)} - {template.title} ({status_text}) - 意向类别：{response.intended_category}"
            rows.append(
                ("活动问卷", response.student_id, response.student_name, response.phone, response.wechat, remark, format_datetime(response.submit_time))
            )
    rows.sort(key=lambda row: row[6], reverse=True)
    filename = f"questionnaires_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_file_response(filename, ["类型", "学号", "姓名", "手机号", "微信号", "备注", "提交时间"], rows)


@admin_questionnaires_bp.get("/api/admin/registration_questionnaires")
@require_system_admin
def registration_questionnaires():
    items = [
        _registration_payload(item)
        for item in RegistrationQuestionnaire.query.order_by(RegistrationQuestionnaire.submit_time.desc()).all()
    ]
    return jsonify({"success": True, "questionnaires": items, "total": len(items)})


@admin_questionnaires_bp.get("/api/admin/registration_questionnaires/export")
@require_system_admin
def export_registration_questionnaires():
    rows = (
        (item.student_id, item.name, item.phone, item.wechat, item.suggestion, format_datetime(item.submit_time))
        for item in RegistrationQuestionnaire.query.order_by(RegistrationQuestionnaire.submit_time.desc()).all()
    )
    filename = f"registration_questionnaires_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_file_response(filename, ["学号", "姓名", "手机号", "微信号", "建议", "提交时间"], rows)
