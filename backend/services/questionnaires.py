"""Questionnaire business rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from backend.extensions import db
from backend.models import ActivityQuestionnaire
from backend.services.legacy_import import FORM_DATETIME_FORMAT, parse_datetime


QUESTION_TYPES = {"description", "single_choice", "multiple_choice", "text", "textarea"}


def normalize_custom_questions(questions: list[dict[str, Any]], preserve_ids: bool = False) -> tuple[list[dict[str, Any]] | None, str | None]:
    normalized = []
    for index, item in enumerate(questions):
        question = dict(item)
        if not preserve_ids or not question.get("question_id"):
            question["question_id"] = str(uuid.uuid4())
        question["order"] = index + 1
        if question.get("question_type") not in QUESTION_TYPES:
            return None, f"题目{index + 1}类型无效"
        if not question.get("question_text"):
            return None, f"题目{index + 1}文本不能为空"
        normalized.append(question)
    return normalized, None


def parse_form_datetime(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, FORM_DATETIME_FORMAT)
    except (TypeError, ValueError):
        parsed = parse_datetime(value)
        return parsed


def validate_template_window(start_value: str, end_value: str) -> tuple[datetime | None, datetime | None, str | None]:
    if not start_value or not end_value:
        return None, None, "请设置问卷时间"
    try:
        start = parse_form_datetime(start_value)
        end = parse_form_datetime(end_value)
    except ValueError:
        return None, None, "时间格式不正确"
    if start is None or end is None:
        return None, None, "请设置问卷时间"
    if start >= end:
        return None, None, "开始时间必须早于结束时间"
    return start, end, None


def template_is_open(template: ActivityQuestionnaire, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return template.status == "active" and template.start_time <= now <= template.end_time
