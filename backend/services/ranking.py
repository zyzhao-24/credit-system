"""Questionnaire ranking and waitlist helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.models import ActivityQuestionnaire, QuestionnaireResponse
from backend.services.legacy_import import DATETIME_FORMAT


def format_datetime(value: datetime | None) -> str:
    return value.strftime(DATETIME_FORMAT) if value else ""


def active_rank_map(questionnaire_id: str) -> dict[str, int]:
    """活动排名：按提交顺序；被管理员标记缺席的报名不占名额，候补按顺序自动转正。"""
    responses = (
        QuestionnaireResponse.query.filter_by(questionnaire_id=questionnaire_id, status="active")
        .order_by(QuestionnaireResponse.submit_time.asc(), QuestionnaireResponse.response_pk.asc())
        .all()
    )
    present = [response for response in responses if not getattr(response, "absent", False)]
    return {response.response_id: index for index, response in enumerate(present, 1)}


def response_status(response: QuestionnaireResponse, questionnaire: ActivityQuestionnaire, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    absent = bool(getattr(response, "absent", False))
    ranks = active_rank_map(response.questionnaire_id)
    rank = ranks.get(response.response_id, 0) if response.status == "active" else 0
    is_waitlist = False
    is_selected = False
    if response.status == "active" and not absent:
        if questionnaire.max_participants > 0:
            is_selected = rank <= questionnaire.max_participants
            is_waitlist = rank > questionnaire.max_participants
        else:
            is_selected = True
    return {
        "rank": rank,
        "is_waitlist": is_waitlist,
        "is_selected": is_selected,
        "is_ended": now > questionnaire.end_time,
        "absent": absent,
    }


def checkin_state(response: QuestionnaireResponse, status: dict[str, Any]) -> str:
    """签到状态：absent 缺席 / none 未签到 / pending 候补待确认 / valid 已签到。"""
    if response.status != "active":
        return "none"
    if status.get("absent"):
        return "absent"
    if not getattr(response, "checked_in_at", None):
        return "none"
    if status["is_selected"] or getattr(response, "checkin_confirmed", False):
        return "valid"
    return "pending"


def response_payload(response: QuestionnaireResponse, questionnaire: ActivityQuestionnaire) -> dict[str, Any]:
    status = response_status(response, questionnaire)
    return {
        "response_id": response.response_id,
        "questionnaire_id": response.questionnaire_id,
        "student_id": response.student_id,
        "student_name": response.student_name,
        "phone": response.phone,
        "wechat": response.wechat,
        "intended_category": response.intended_category,
        "custom_answers": response.custom_answers or {},
        "template_snapshot": response.template_snapshot or None,
        "template_version": response.template_version,
        "submit_time": format_datetime(response.submit_time),
        "status": response.status,
        "checked_in_at": format_datetime(getattr(response, "checked_in_at", None)),
        "checkin_confirmed": bool(getattr(response, "checkin_confirmed", False)),
        "checkin_state": checkin_state(response, status),
        **status,
    }
