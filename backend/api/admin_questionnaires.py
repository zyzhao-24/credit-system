"""Questionnaire administration API."""

from __future__ import annotations

import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth.decorators import require_admin, require_system_admin
from backend.extensions import db
from backend.models import (
    Activity,
    ActivityQuestionnaire,
    QuestionnaireResponse,
    Record,
)
from backend.services.exporters import xlsx_file_response
from backend.services.permissions import check_activity_edit_permission
from backend.services.questionnaires import (
    assign_checkin_codes,
    bound_record,
    clear_checkin_codes,
    generate_checkin_code,
    normalize_body,
    normalize_custom_questions,
    questionnaire_has_category_question,
    record_categories,
    template_body,
    validate_template_window,
)
from backend.services.ranking import format_datetime, response_payload, response_status
from backend.services.students import PHONE_PATTERN


admin_questionnaires_bp = Blueprint("admin_questionnaires", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _forbidden(template: ActivityQuestionnaire) -> bool:
    """问卷权限：绑定活动的问卷权限同活动（编辑者即可管理）；独立问卷仅限系统管理员。"""
    identity = g.current_identity
    if identity.get("role") == "system_admin":
        return False
    if template.is_standalone:
        return True
    return not check_activity_edit_permission(identity, template.activity_id)


def _activity_name(activity_id: str) -> str:
    if not activity_id:
        return "独立问卷"
    activity = db.session.get(Activity, activity_id)
    return activity.name if activity else "未知活动"


def _template_payload(item: ActivityQuestionnaire) -> dict:
    response_count = QuestionnaireResponse.query.filter_by(
        questionnaire_id=item.questionnaire_id,
        status="active",
    ).count()
    record = bound_record(item)
    categories = list(record.categories) if record else []
    return {
        "questionnaire_id": item.questionnaire_id,
        "questionnaire_type": "standalone" if item.is_standalone else "activity_template",
        "title": item.title,
        "activity_name": _activity_name(item.activity_id),
        "activity_id": item.activity_id,
        "record_id": record.record_id if record else "",
        "record_name": record.record_name if record else "",
        "record_categories": categories,
        "start_time": format_datetime(item.start_time),
        "end_time": format_datetime(item.end_time),
        "max_participants": item.max_participants,
        "response_count": response_count,
        "status": item.status,
        "created_time": format_datetime(item.created_time),
        "is_ended": datetime.now() > item.end_time,
        "has_category_question": len(categories) >= 2,
        "custom_questions": item.custom_questions or [],
        "body": template_body(item),
        "version": item.version,
        # 签到会话开关（每人独立的一次性签到码在填写记录中展示）
        "checkin_open": bool(getattr(item, "checkin_open", False)),
    }


def _resolve_record(activity_id: str, record_id: str) -> tuple[Record | None, str | None]:
    """校验问卷绑定的记录：选了活动必须选记录，且记录须属于该活动。"""
    if not activity_id:
        return None, None  # 独立问卷不绑定记录
    if not record_id:
        return None, "请选择绑定的记录"
    record = db.session.get(Record, record_id)
    if record is None or record.activity_id != activity_id:
        return None, "记录不存在或不属于该活动"
    return record, None


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
@require_admin
def all_questionnaires():
    """列出问卷模板：系统管理员看全部；普通管理员只看其可编辑活动绑定的问卷。"""
    identity = g.current_identity
    items = ActivityQuestionnaire.query.all()
    if identity.get("role") != "system_admin":
        items = [
            item
            for item in items
            if not item.is_standalone and check_activity_edit_permission(identity, item.activity_id)
        ]
    questionnaires = sorted(
        (_template_payload(item) for item in items),
        key=lambda item: item.get("created_time", ""),
        reverse=True,
    )
    return jsonify({"success": True, "questionnaires": questionnaires, "total": len(questionnaires)})


@admin_questionnaires_bp.put("/api/admin/questionnaire/update")
@require_admin
def update_questionnaire():
    data = request.get_json(silent=True) or {}
    questionnaire_id = data.get("questionnaire_id", "")

    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template:
        if _forbidden(template):
            return _error("无权限操作该问卷", 403)
        status = data.get("status", template.status)
        if status not in {"active", "closed"}:
            return _error("问卷状态不正确")
        template.status = status
        db.session.commit()
        return jsonify({"success": True, "message": "更新成功"})
    return _error("问卷不存在")


@admin_questionnaires_bp.delete("/api/admin/questionnaire/<questionnaire_id>")
@require_admin
def delete_questionnaire(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template:
        if _forbidden(template):
            return _error("无权限操作该问卷", 403)
        activity_id = template.activity_id
        db.session.delete(template)
        db.session.flush()
        _sync_activity_questionnaire_fields(activity_id)
        db.session.commit()
        return jsonify({"success": True, "message": "删除成功"})
    return _error("问卷不存在")


@admin_questionnaires_bp.post("/api/admin/questionnaire/create_template")
@require_admin
def create_template():
    data = request.get_json(silent=True) or {}
    activity_id = data.get("activity_id", "").strip()
    title = data.get("title", "").strip()
    standalone = not activity_id
    if standalone:
        # 未绑定活动的问卷仅系统管理员可创建
        if g.current_identity.get("role") != "system_admin":
            return _error("独立问卷仅系统管理员可以创建", 403)
    elif db.session.get(Activity, activity_id) is None:
        return _error("活动不存在")
    elif not check_activity_edit_permission(g.current_identity, activity_id):
        return _error("无权限为该活动创建问卷", 403)
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
    if not standalone and ActivityQuestionnaire.query.filter_by(
        activity_id=activity_id, status="active"
    ).first():
        return _error("该活动已存在问卷")
    record, error = _resolve_record(activity_id, data.get("record_id", "").strip())
    if error:
        return _error(error)
    questions, error = normalize_custom_questions(data.get("custom_questions", []))
    if error:
        return _error(error)
    body, error = normalize_body(data.get("body"), questions)
    if error:
        return _error(error)

    template = ActivityQuestionnaire(
        questionnaire_id=str(uuid.uuid4()),
        activity_id=activity_id,
        record_id=record.record_id if record else "",
        title=title,
        start_time=start,
        end_time=end,
        max_participants=max_participants,
        # 意向类别题由绑定记录的类别自动生成（多类别才出现）
        has_category_question=len(record.categories) >= 2 if record else False,
        custom_questions=questions,
        body=body,
        created_time=datetime.now(),
        status="active",
    )
    db.session.add(template)
    db.session.flush()
    if not standalone:
        _sync_activity_questionnaire_fields(activity_id)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("该活动已存在问卷")
    return jsonify({"success": True, "message": "创建成功", "questionnaire_id": template.questionnaire_id})


@admin_questionnaires_bp.put("/api/admin/questionnaire/template/<questionnaire_id>")
@require_admin
def update_template(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if _forbidden(template):
        return _error("无权限操作该问卷", 403)
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
    body, error = normalize_body(data.get("body"), questions)
    if error:
        return _error(error)
    record_id = data.get("record_id", "").strip()
    record, error = _resolve_record(template.activity_id, record_id)
    if error:
        return _error(error)

    # 标题、题目、正文或绑定记录发生变化时版本号 +1；历史提交通过快照绑定旧版本
    new_record_id = record.record_id if record else ""
    content_changed = (
        title != template.title
        or questions != (template.custom_questions or [])
        or body != template_body(template)
        or new_record_id != (template.record_id or "")
    )
    template.title = title
    template.start_time = start
    template.end_time = end
    template.max_participants = max_participants
    template.record_id = new_record_id
    template.has_category_question = questionnaire_has_category_question(template)
    template.custom_questions = questions
    template.body = body
    if content_changed:
        template.version = (template.version or 1) + 1
    if not template.is_standalone:
        _sync_activity_questionnaire_fields(template.activity_id)
    db.session.commit()
    return jsonify({"success": True, "message": "更新成功", "version": template.version})


@admin_questionnaires_bp.delete("/api/admin/questionnaire/template/<questionnaire_id>")
@require_admin
def delete_template(questionnaire_id: str):
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if _forbidden(template):
        return _error("无权限操作该问卷", 403)
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
    if _forbidden(template):
        return _error("无权限查看该问卷", 403)
    responses = []
    for response in QuestionnaireResponse.query.filter_by(questionnaire_id=questionnaire_id).all():
        payload = response_payload(response, template)
        # 每人独立的一次性签到码，仅管理端可见（学生端不下发，防止远程代签）
        payload["checkin_code"] = getattr(response, "checkin_code", "") or ""
        responses.append(payload)
    responses.sort(key=lambda item: (item["status"] != "active", item["submit_time"]))
    return jsonify({"success": True, "responses": responses})


@admin_questionnaires_bp.get("/api/admin/questionnaire/responses/<questionnaire_id>/export")
@require_admin
def export_responses(questionnaire_id: str):
    """导出填写记录为 xlsx：基本信息 + 状态 + 每道题目的答案各一列。

    答案列以提交时保存的问卷快照为准（模板修改后历史提交仍能对应到原题目），
    列集合取当前模板与所有快照题目的并集（按题目 ID 去重、保持顺序）。
    """
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if _forbidden(template):
        return _error("无权限导出该问卷", 403)

    responses = QuestionnaireResponse.query.filter_by(questionnaire_id=questionnaire_id).all()
    question_columns: list[tuple[str, str]] = []  # (question_id, question_text)
    seen: set[str] = set()

    def _collect(questions: list[dict]) -> None:
        for question in questions:
            if question.get("question_type") == "description":
                continue
            qid = question.get("question_id")
            if qid and qid not in seen:
                seen.add(qid)
                question_columns.append((qid, question.get("question_text", "")))

    _collect(template.custom_questions or [])
    for response in responses:
        snapshot = response.template_snapshot or {}
        _collect(snapshot.get("custom_questions", []))

    def _answer_text(response: QuestionnaireResponse, question_id: str) -> str:
        answer = (response.custom_answers or {}).get(question_id, {}).get("answer")
        if answer is None:
            return ""
        if isinstance(answer, list):
            return "、".join(str(item) for item in answer)
        return str(answer)

    rows = []
    for response in responses:
        payload = response_payload(response, template)
        status = response_status(response, template)
        if response.status == "cancelled":
            status_text = "已取消"
        elif status["is_ended"]:
            status_text = "成功" if status["is_selected"] else "失败"
        else:
            status_text = "候补" if status["is_waitlist"] else "成功"
        checkin_text = {
            "absent": "缺席",
            "valid": "已签到",
            "pending": "待确认（候补）",
        }.get(payload["checkin_state"], "未签到")
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
                response.template_version or "",
                checkin_text,
                payload["checked_in_at"],
                *(_answer_text(response, qid) for qid, _ in question_columns),
            )
        )
    rows.sort(key=lambda row: (row[7] == "已取消", row[6]))
    safe_title = (
        template.title.replace(",", "_").replace("\n", "_").replace("\r", "_").replace("/", "_")
    )
    return xlsx_file_response(
        f"{safe_title}_填写记录.xlsx",
        safe_title[:31] or "填写记录",
        ["排名", "学号", "姓名", "手机号", "微信号", "意向学分类别", "提交时间", "状态", "问卷版本", "签到", "签到时间"]
        + [text for _, text in question_columns],
        rows,
    )


@admin_questionnaires_bp.put("/api/admin/questionnaire/response/<response_id>")
@require_admin
def update_response(response_id: str):
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template is None or _forbidden(template):
        return _error("无权限操作该问卷", 403)
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    if phone:
        if not PHONE_PATTERN.fullmatch(phone):
            return _error("手机号格式不正确")
        response.phone = phone
    if data.get("wechat"):
        response.wechat = data["wechat"].strip()
    if "intended_category" in data:
        template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
        categories = record_categories(template) if template else []
        category = data.get("intended_category", "").strip()
        # 管理端可改意向类别，但仍限于记录的可行类别（多类别时允许"无"）
        if categories and len(categories) >= 2 and category not in categories and category != "无":
            return _error("意向类别不在该记录的可行类别中")
        response.intended_category = category
    db.session.commit()
    return jsonify({"success": True, "message": "修改成功"})


@admin_questionnaires_bp.delete("/api/admin/questionnaire/response/<response_id>")
@require_admin
def delete_response(response_id: str):
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template is None or _forbidden(template):
        return _error("无权限操作该问卷", 403)
    db.session.delete(response)
    db.session.commit()
    return jsonify({"success": True, "message": "删除成功"})


# ========== 现场签到 ==========


@admin_questionnaires_bp.post("/api/admin/questionnaire/<questionnaire_id>/checkin/open")
@require_admin
def open_checkin(questionnaire_id: str):
    """开启签到：为每位未签到的报名者分配独立的 6 位一次性签到码。

    码只对本人有效（签到时校验本人报名的码），签到成功后立即作废；
    管理员在填写记录的"签到码"列现场展示或抄给学生。
    """
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if _forbidden(template):
        return _error("无权限操作该问卷", 403)
    template.checkin_open = True
    template.checkin_code = ""  # 旧的共享码字段废弃，确保清空
    assigned = assign_checkin_codes(template)
    db.session.commit()
    return jsonify({"success": True, "message": f"签到已开启，已分配 {assigned} 个签到码"})


@admin_questionnaires_bp.post("/api/admin/questionnaire/<questionnaire_id>/checkin/close")
@require_admin
def close_checkin(questionnaire_id: str):
    """关闭签到：作废全部未使用的签到码（已签到记录不受影响）。"""
    template = db.session.get(ActivityQuestionnaire, questionnaire_id)
    if template is None:
        return _error("问卷不存在")
    if _forbidden(template):
        return _error("无权限操作该问卷", 403)
    template.checkin_open = False
    template.checkin_code = ""
    clear_checkin_codes(questionnaire_id)
    db.session.commit()
    return jsonify({"success": True, "message": "签到已关闭"})


@admin_questionnaires_bp.post("/api/admin/questionnaire/response/<response_id>/checkin/confirm")
@require_admin
def confirm_checkin(response_id: str):
    """管理员确认/标记签到：候补的待确认签到确认生效；未签到的直接代签成功。

    代签无需签到码（管理员现场确认），签到码同时作废；缺席的报名需先取消缺席标记。
    """
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template is None or _forbidden(template):
        return _error("无权限操作该问卷", 403)
    if response.status != "active":
        return _error("该报名已取消")
    if getattr(response, "absent", False):
        return _error("该学生已被标记为缺席，请先取消缺席标记")
    if response.checked_in_at:
        response.checkin_confirmed = True
        message = "签到已确认"
    else:
        # 管理员直接代签：立即生效（管理员确认视为已确认，不受候补待确认限制）
        response.checked_in_at = datetime.now()
        response.checkin_confirmed = True
        message = "已标记签到成功"
    response.checkin_code = ""  # 一次性码作废
    db.session.commit()
    return jsonify({"success": True, "message": message})


@admin_questionnaires_bp.post("/api/admin/questionnaire/response/<response_id>/checkin/code")
@require_admin
def generate_response_checkin_code(response_id: str):
    """为单个报名者手动生成一次性签到码（候补默认不分配，由管理员逐人生成）。"""
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template is None or _forbidden(template):
        return _error("无权限操作该问卷", 403)
    if response.status != "active":
        return _error("该报名已取消")
    if response.checked_in_at:
        return _error("该学生已签到，无需签到码")
    if not getattr(template, "checkin_open", False):
        return _error("签到未开启，请先开启签到")
    if not getattr(response, "checkin_code", ""):
        response.checkin_code = generate_checkin_code(template.questionnaire_id)
        db.session.commit()
    return jsonify(
        {"success": True, "message": "签到码已生成", "checkin_code": response.checkin_code}
    )


@admin_questionnaires_bp.post("/api/admin/questionnaire/response/<response_id>/checkin/cancel")
@require_admin
def cancel_checkin(response_id: str):
    """取消学生的签到：清除签到记录，恢复为"未签到"。

    签到仍开启时补发一个新的一次性签到码，学生可重新签到；
    取消后才能标记缺席（已签到不能直接标记缺席）。
    """
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template is None or _forbidden(template):
        return _error("无权限操作该问卷", 403)
    if not response.checked_in_at:
        return _error("该学生尚未签到")
    response.checked_in_at = None
    response.checkin_confirmed = False
    if getattr(template, "checkin_open", False):
        response.checkin_code = generate_checkin_code(template.questionnaire_id)
    db.session.commit()
    return jsonify({"success": True, "message": "已取消签到，该学生可重新签到"})


@admin_questionnaires_bp.post("/api/admin/questionnaire/response/<response_id>/absent")
@require_admin
def toggle_absent(response_id: str):
    """标记/取消缺席：缺席不占名额，候补按顺序自动转正。"""
    response = QuestionnaireResponse.query.filter_by(response_id=response_id).first()
    if response is None:
        return _error("记录不存在")
    template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
    if template is None or _forbidden(template):
        return _error("无权限操作该问卷", 403)
    data = request.get_json(silent=True) or {}
    absent = bool(data.get("absent", True))
    if absent and response.checked_in_at:
        return _error("该学生已签到，请先取消签到再标记缺席")
    response.absent = absent
    db.session.commit()
    return jsonify({"success": True, "message": "已标记缺席" if absent else "已取消缺席标记"})


@admin_questionnaires_bp.get("/api/admin/questionnaires/export")
@require_system_admin
def export_all_questionnaires():
    rows = []
    for response in QuestionnaireResponse.query.all():
        template = db.session.get(ActivityQuestionnaire, response.questionnaire_id)
        if not template:
            continue
        status_text = "成功" if response.status == "active" else "已取消"
        type_text = "独立问卷" if template.is_standalone else "活动问卷"
        remark = f"{_activity_name(template.activity_id)} - {template.title} ({status_text}) - 意向类别：{response.intended_category}"
        rows.append(
            (type_text, response.student_id, response.student_name, response.phone, response.wechat, remark, format_datetime(response.submit_time))
        )
    rows.sort(key=lambda row: row[6], reverse=True)
    filename = f"questionnaires_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return xlsx_file_response(filename, "问卷填写记录", ["类型", "学号", "姓名", "手机号", "微信号", "备注", "提交时间"], rows)
