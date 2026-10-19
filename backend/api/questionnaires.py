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
    Student,
)
from backend.services.questionnaires import (
    bound_record,
    generate_checkin_code,
    record_categories,
    resolve_intended_category,
    template_body,
    template_is_open,
    template_snapshot,
    validate_answers,
)
from backend.services.ranking import (
    active_rank_map,
    format_datetime,
    response_payload,
    response_status,
)


questionnaires_bp = Blueprint("questionnaires", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _activity_name(activity_id: str) -> str:
    if not activity_id:
        return "独立问卷"
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
        record = bound_record(template)
        categories = list(record.categories) if record else []
        result.append(
            {
                "questionnaire_id": template.questionnaire_id,
                "activity_id": template.activity_id,
                "title": template.title,
                "activity_name": _activity_name(template.activity_id),
                "record_id": record.record_id if record else "",
                "record_name": record.record_name if record else "",
                "record_categories": categories,
                "start_time": format_datetime(template.start_time),
                "end_time": format_datetime(template.end_time),
                "max_participants": template.max_participants,
                "response_count": len(responses),
                "is_registered": mine is not None,
                "my_rank": rank,
                "is_waitlist": bool(
                    mine and template.max_participants > 0 and rank > template.max_participants
                ),
                "has_category_question": len(categories) >= 2,
                "custom_questions": template.custom_questions or [],
                "body": template_body(template),
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
                # 签到是否开启（学生据此显示签到入口）
                "checkin_open": bool(getattr(template, "checkin_open", False)),
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

    phone = student.phone
    wechat = student.wechat
    if not phone or not wechat:
        return _error("请先在报名信息中填写手机号和微信号")
    # 意向类别由绑定记录解析：单类别自动归入，多类别缺省为"无"
    intended_category, category_error = resolve_intended_category(template, intended_category)
    if category_error:
        return _error(category_error)
    answer_error = validate_answers(template.custom_questions or [], custom_answers)
    if answer_error:
        return _error(answer_error)

    existing = QuestionnaireResponse.query.filter_by(
        questionnaire_id=questionnaire_id,
        student_id=student_id,
    ).first()
    if existing and existing.status == "active":
        return _error("您已报名此问卷")

    snapshot = template_snapshot(template)
    try:
        if existing:
            existing.phone = phone
            existing.wechat = wechat
            existing.intended_category = intended_category
            existing.custom_answers = custom_answers
            existing.template_snapshot = snapshot
            existing.template_version = template.version
            existing.submit_time = now
            existing.status = "active"
            target = existing
        else:
            target = QuestionnaireResponse(
                response_id=str(uuid.uuid4()),
                questionnaire_id=questionnaire_id,
                student_id=student_id,
                student_name=student.name,
                phone=phone,
                wechat=wechat,
                intended_category=intended_category,
                custom_answers=custom_answers,
                template_snapshot=snapshot,
                template_version=template.version,
                submit_time=now,
                status="active",
            )
            db.session.add(target)
        db.session.flush()
        # 签到开启期间的新报名（含取消后重报）：名额内自动补发一次性签到码；
        # 候补默认不发码，需要时由管理员逐人生成
        if getattr(template, "checkin_open", False) and not target.checked_in_at:
            if not response_status(target, template)["is_waitlist"]:
                target.checkin_code = generate_checkin_code(template.questionnaire_id)
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
    custom_answers = data.get("custom_answers", {})
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template:
        resolved, category_error = resolve_intended_category(template, intended_category)
        if category_error:
            return _error(category_error)
        intended_category = resolved
        answer_error = validate_answers(template.custom_questions or [], custom_answers)
        if answer_error:
            return _error(answer_error)
        response.template_snapshot = template_snapshot(template)
        response.template_version = template.version
    response.intended_category = intended_category
    response.custom_answers = custom_answers
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


@questionnaires_bp.post("/api/student/questionnaire/<questionnaire_id>/checkin")
@require_student
def checkin(questionnaire_id: str):
    """现场签到：输入本人报名对应的一次性签到码（管理员处获取或扫码带入）。

    名额内（成功）学生签到即生效；候补学生的签到记录为"待确认"，
    待管理员确认、或因缺席转正后自动生效。签到成功后该码立即作废。
    """
    student_id = g.current_identity.get("sub")
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if not getattr(template, "checkin_open", False):
        return _error("签到未开启")

    response = QuestionnaireResponse.query.filter_by(
        questionnaire_id=questionnaire_id, student_id=student_id, status="active"
    ).first()
    if response is None:
        return _error("您尚未报名该活动")
    if getattr(response, "absent", False):
        return _error("您已被标记为缺席，如有疑问请联系管理员")
    if response.checked_in_at:
        return jsonify({"success": True, "message": "您已签到过", "checkin_state": None})

    # 每人独立的一次性码：必须与本人报名的码一致，别人的码无效
    code = (request.get_json(silent=True) or {}).get("code", "").strip()
    if not code or code != (getattr(response, "checkin_code", "") or ""):
        return _error("签到码不正确")

    # 候补与名额内一致：签到即生效
    response.checked_in_at = datetime.now()
    response.checkin_confirmed = True
    # 一次性：签到成功后立即作废
    response.checkin_code = ""
    db.session.commit()
    return jsonify({"success": True, "message": "签到成功", "checkin_state": "valid"})
