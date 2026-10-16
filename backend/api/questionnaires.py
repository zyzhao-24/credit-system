"""Student questionnaire registration API."""

from __future__ import annotations

import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth.decorators import require_student
from backend.extensions import db
from backend.models import (
    Activity,
    ActivityQuestionnaire,
    QuestionnaireResponse,
    RegistrationQuestionnaire,
    Student,
)
from backend.services.questionnaires import template_is_open
from backend.services.ranking import active_rank_map, format_datetime, response_payload


questionnaires_bp = Blueprint("questionnaires", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _activity_name(activity_id: str) -> str:
    activity = db.session.get(Activity, activity_id)
    return activity.name if activity else "未知活动"


@questionnaires_bp.get("/api/student/questionnaires/available")
@require_student
def available_questionnaires():
    now = datetime.now()
    student_id = g.current_identity.get("sub")
    templates = ActivityQuestionnaire.query.filter_by(status="active").all()
    result = []
    for template in templates:
        if not template_is_open(template, now):
            continue
        responses = QuestionnaireResponse.query.filter_by(
            questionnaire_id=template.questionnaire_id,
            status="active",
        ).all()
        mine = next((item for item in responses if item.student_id == student_id), None)
        rank = active_rank_map(template.questionnaire_id).get(mine.response_id, 0) if mine else 0
        result.append(
            {
                "questionnaire_id": template.questionnaire_id,
                "activity_id": template.activity_id,
                "title": template.title,
                "activity_name": _activity_name(template.activity_id),
                "start_time": format_datetime(template.start_time),
                "end_time": format_datetime(template.end_time),
                "max_participants": template.max_participants,
                "response_count": len(responses),
                "is_registered": mine is not None,
                "my_rank": rank,
                "is_waitlist": bool(
                    mine and template.max_participants > 0 and rank > template.max_participants
                ),
                "has_category_question": template.has_category_question,
                "custom_questions": template.custom_questions or [],
            }
        )
    result.sort(key=lambda item: item["start_time"], reverse=True)
    return jsonify({"success": True, "questionnaires": result})


@questionnaires_bp.get("/api/student/questionnaires/my_registrations")
@require_student
def my_registrations():
    student_id = g.current_identity.get("sub")
    responses = (
        QuestionnaireResponse.query.filter_by(student_id=student_id)
        .order_by(QuestionnaireResponse.submit_time.desc())
        .all()
    )
    registrations = []
    for response in responses:
        template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
        if template is None:
            continue
        payload = response_payload(response, template)
        payload.update(
            {
                "questionnaire_title": template.title,
                "activity_name": _activity_name(template.activity_id),
                "max_participants": template.max_participants,
            }
        )
        registrations.append(payload)
    return jsonify({"success": True, "registrations": registrations})


@questionnaires_bp.post("/api/student/questionnaire/submit")
@require_student
def submit_questionnaire():
    student_id = g.current_identity.get("sub")
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("学生不存在，请联系管理员")

    data = request.get_json(silent=True) or {}
    questionnaire_id = data.get("questionnaire_id", "").strip()
    intended_category = data.get("intended_category", "").strip()
    custom_answers = data.get("custom_answers", {})
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if template.status != "active":
        return _error("问卷已关闭")
    now = datetime.now()
    if now < template.start_time:
        return _error("问卷尚未开始")
    if now > template.end_time:
        return _error("问卷已截止")

    registration = RegistrationQuestionnaire.query.filter_by(student_id=student_id).first()
    phone = registration.phone if registration else ""
    wechat = registration.wechat if registration else ""
    if not phone or not wechat:
        return _error("请先在注册问卷中填写手机号和微信号")
    if template.has_category_question and not intended_category:
        return _error("请选择意向学分类别")

    existing = QuestionnaireResponse.query.filter_by(
        questionnaire_id=questionnaire_id,
        student_id=student_id,
    ).first()
    if existing and existing.status == "active":
        return _error("您已报名此问卷")

    try:
        if existing:
            existing.phone = phone
            existing.wechat = wechat
            existing.intended_category = intended_category
            existing.custom_answers = custom_answers
            existing.submit_time = now
            existing.status = "active"
        else:
            db.session.add(
                QuestionnaireResponse(
                    response_id=str(uuid.uuid4()),
                    questionnaire_id=questionnaire_id,
                    student_id=student_id,
                    student_name=student.name,
                    phone=phone,
                    wechat=wechat,
                    intended_category=intended_category,
                    custom_answers=custom_answers,
                    submit_time=now,
                    status="active",
                )
            )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("您已报名此问卷")
    return jsonify({"success": True, "message": "报名成功"})


@questionnaires_bp.put("/api/student/questionnaire/update/<response_id>")
@require_student
def update_questionnaire_response(response_id: str):
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    if response.student_id != g.current_identity.get("sub"):
        return _error("无权限", 403)
    if response.status != "active":
        return _error("已取消的报名无法修改")

    data = request.get_json(silent=True) or {}
    intended_category = data.get("intended_category", "").strip()
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template and template.has_category_question and not intended_category:
        return _error("请选择意向学分类别")
    response.intended_category = intended_category
    response.custom_answers = data.get("custom_answers", {})
    db.session.commit()
    return jsonify({"success": True, "message": "修改成功"})


@questionnaires_bp.post("/api/student/questionnaire/cancel/<response_id>")
@require_student
def cancel_questionnaire(response_id: str):
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    if response.student_id != g.current_identity.get("sub"):
        return _error("无权限", 403)
    if response.status != "active":
        return _error("已取消，无需重复操作")
    response.status = "cancelled"
    db.session.commit()
    return jsonify({"success": True, "message": "取消成功"})
