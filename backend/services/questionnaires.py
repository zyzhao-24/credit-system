"""Questionnaire business rules."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime
from typing import Any

from backend.extensions import db  # noqa: F401  (re-exported for legacy callers)
from backend.models import ActivityQuestionnaire, QuestionnaireResponse, Record
from backend.services.legacy_import import FORM_DATETIME_FORMAT, parse_datetime


QUESTION_TYPES = {
    "description",       # 说明文字（无需作答）
    "single_choice",     # 单选
    "multiple_choice",   # 多选
    "text",              # 文本（单行填空 / 多行简答由 multiline 区分）
    "textarea",          # 旧数据兼容：等同 text + multiline
    "number",            # 数字
    "date",              # 日期
    "rating",            # 评分（1..max_rating）
}

CHOICE_TYPES = {"single_choice", "multiple_choice"}

# 文本题的格式校验预设
TEXT_FORMATS = {"none", "phone", "email", "idcard", "regex"}
_FORMAT_PATTERNS = {
    "phone": (re.compile(r"^1[3-9]\d{9}$"), "手机号格式不正确"),
    "email": (re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$"), "邮箱格式不正确"),
    "idcard": (re.compile(r"^\d{17}[\dXx]$"), "身份证号格式不正确"),
}

# 选择题"其他"自定义项的答案前缀
OTHER_PREFIX = "其他："


def normalize_custom_questions(questions: list[dict[str, Any]], preserve_ids: bool = False) -> tuple[list[dict[str, Any]] | None, str | None]:
    normalized = []
    for index, item in enumerate(questions):
        question = dict(item)
        # 正文槽位按 question_id 引用题目，客户端提供的 ID 一律保留，缺省时生成
        if not question.get("question_id"):
            question["question_id"] = str(uuid.uuid4())
        question["order"] = index + 1
        question_type = question.get("question_type")
        if question_type not in QUESTION_TYPES:
            return None, f"题目{index + 1}类型无效"
        if not question.get("question_text"):
            return None, f"题目{index + 1}文本不能为空"
        question["required"] = bool(question.get("required", False))
        if question_type in CHOICE_TYPES:
            options = [str(option).strip() for option in question.get("options", []) if str(option).strip()]
            if len(options) < 2:
                return None, f"题目{index + 1}至少需要2个选项"
            if len(set(options)) != len(options):
                return None, f"题目{index + 1}的选项重复"
            question["options"] = options
            # 允许"其他"：学生可选择并自由填写
            question["allow_other"] = bool(question.get("allow_other", False))
        else:
            question["options"] = []
            question["allow_other"] = False
        if question_type == "rating":
            try:
                max_rating = int(question.get("max_rating") or 5)
            except (TypeError, ValueError):
                return None, f"题目{index + 1}的评分上限必须是数字"
            if not 2 <= max_rating <= 10:
                return None, f"题目{index + 1}的评分上限需在 2-10 之间"
            question["max_rating"] = max_rating
        else:
            question["max_rating"] = 0
        if question_type == "number":
            bounds: dict[str, float | None] = {}
            for key in ("min_value", "max_value"):
                raw = question.get(key)
                if raw in (None, ""):
                    bounds[key] = None
                    continue
                try:
                    bounds[key] = float(raw)
                except (TypeError, ValueError):
                    return None, f"题目{index + 1}的数值范围必须是数字"
            if (
                bounds["min_value"] is not None
                and bounds["max_value"] is not None
                and bounds["min_value"] > bounds["max_value"]
            ):
                return None, f"题目{index + 1}的最小值不能大于最大值"
            question["min_value"] = bounds["min_value"]
            question["max_value"] = bounds["max_value"]
        else:
            question["min_value"] = None
            question["max_value"] = None
        if question_type in {"text", "textarea"}:
            try:
                max_length = int(question.get("max_length") or (200 if question_type == "text" else 500))
            except (TypeError, ValueError):
                return None, f"题目{index + 1}的最大字符数必须是数字"
            question["max_length"] = max(1, min(max_length, 5000))
            # 填空/简答合并为文本题：textarea 等同多行文本
            question["multiline"] = question_type == "textarea" or bool(question.get("multiline"))
            text_format = question.get("format") or "none"
            if text_format not in TEXT_FORMATS:
                return None, f"题目{index + 1}的格式校验无效"
            pattern = str(question.get("pattern") or "")
            if text_format == "regex":
                if not pattern:
                    return None, f"题目{index + 1}选择自定义正则时必须填写表达式"
                try:
                    re.compile(pattern)
                except re.error:
                    return None, f"题目{index + 1}的正则表达式无效"
            question["format"] = text_format
            question["pattern"] = pattern if text_format == "regex" else ""
        else:
            question["max_length"] = 0
            question["multiline"] = False
            question["format"] = "none"
            question["pattern"] = ""
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


# ========== 正文文档（文字与题目槽位混排） ==========

def synthesize_body(questions: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """为没有正文的旧模板合成文档：说明文字变文本段，其余题目各占一段。"""
    body: list[list[dict[str, Any]]] = []
    for question in questions:
        if question.get("question_type") == "description":
            text = str(question.get("question_text", "")).strip()
            if text:
                body.append([{"type": "text", "text": text}])
        else:
            body.append([{"type": "question", "question_id": question.get("question_id", "")}])
    return body


# 正文可嵌入的信息槽位：提交时自动取学生档案与问卷绑定信息
BODY_FIELDS = {
    "student_name",   # 姓名
    "student_id",     # 学号
    "phone",          # 手机号
    "wechat",         # 微信号
    "activity_name",  # 活动名称
    "record_name",    # 绑定记录名称
    "category",       # 意向类别（多类别记录时为学生的选择题槽位）
}


def normalize_body(
    body: Any, questions: list[dict[str, Any]]
) -> tuple[list[list[dict[str, Any]]] | None, str | None]:
    """校验并规范化正文文档。

    结构：段落数组；每段是片段数组，片段为 {"type":"text","text":str}、
    {"type":"question","question_id":str} 或 {"type":"field","field":str}。
    每道可作答题目必须恰好放入正文一次；信息槽位可重复使用。
    body 为 None 时（旧客户端）按题目顺序合成。
    """
    if body is None:
        return synthesize_body(questions), None
    if not isinstance(body, list):
        return None, "正文格式不正确"
    answerable = {
        question.get("question_id"): question
        for question in questions
        if question.get("question_type") != "description"
    }
    seen: set[str] = set()
    normalized: list[list[dict[str, Any]]] = []
    for p_index, paragraph in enumerate(body):
        if not isinstance(paragraph, list):
            return None, f"第{p_index + 1}段格式不正确"
        parts: list[dict[str, Any]] = []
        for part in paragraph:
            if not isinstance(part, dict):
                return None, f"第{p_index + 1}段格式不正确"
            if part.get("type") == "text":
                text = str(part.get("text", "")).strip()
                if text:
                    parts.append({"type": "text", "text": text})
            elif part.get("type") == "question":
                question_id = str(part.get("question_id", ""))
                if question_id not in answerable:
                    return None, f"第{p_index + 1}段引用了不存在的题目"
                if question_id in seen:
                    return None, f"题目「{answerable[question_id].get('question_text', '')}」被重复放入正文"
                seen.add(question_id)
                parts.append({"type": "question", "question_id": question_id})
            elif part.get("type") == "field":
                field = str(part.get("field", ""))
                if field not in BODY_FIELDS:
                    return None, f"第{p_index + 1}段包含未知的信息槽位"
                parts.append({"type": "field", "field": field})
            else:
                return None, f"第{p_index + 1}段包含未知片段类型"
        if parts:
            normalized.append(parts)
    for index, question in enumerate(questions):
        if question.get("question_type") == "description":
            continue
        if question.get("question_id") not in seen:
            return None, f"题目{index + 1}「{question.get('question_text', '')}」未放入正文"
    return normalized, None


def template_body(template: ActivityQuestionnaire) -> list[list[dict[str, Any]]]:
    """模板的正文文档；旧模板（body 为 NULL）按题目顺序合成。"""
    if template.body is not None:
        return template.body
    return synthesize_body(template.custom_questions or [])


def bound_record(template: ActivityQuestionnaire) -> Record | None:
    """问卷绑定的记录；未绑定、独立问卷或记录不属于该活动时返回 None。"""
    if template.is_standalone or not template.record_id:
        return None
    record = db.session.get(Record, template.record_id)
    if record is None or record.activity_id != template.activity_id:
        return None
    return record


def record_categories(template: ActivityQuestionnaire) -> list[str]:
    record = bound_record(template)
    return list(record.categories) if record else []


def questionnaire_has_category_question(template: ActivityQuestionnaire) -> bool:
    """记录有多个可行类别时自动生成意向类别单选题。"""
    return len(record_categories(template)) >= 2


def resolve_intended_category(template: ActivityQuestionnaire, requested: str) -> tuple[str, str | None]:
    """按绑定记录解析意向类别，返回 (类别, 错误消息)。

    - 未绑定记录/独立问卷：无类别概念，存空串；
    - 记录只有一个类别：无需提问，自动归入该类别；
    - 多个类别：须为记录的候选类别之一，缺省（未作答）时为"无"。
    """
    categories = record_categories(template)
    if not categories:
        return "", None
    if len(categories) == 1:
        return categories[0], None
    requested = requested.strip()
    if not requested or requested == "无":
        return "无", None
    if requested not in categories:
        return "", "意向类别不在该记录的可行类别中"
    return requested, None


def template_snapshot(template: ActivityQuestionnaire) -> dict[str, Any]:
    """提交时随响应保存的问卷快照：模板后续修改不影响历史提交的解读。"""
    record = bound_record(template)
    categories = list(record.categories) if record else []
    return {
        "title": template.title,
        "version": template.version,
        "record_id": record.record_id if record else "",
        "record_name": record.record_name if record else "",
        "record_categories": categories,
        "has_category_question": len(categories) >= 2,
        "custom_questions": template.custom_questions or [],
        "body": template_body(template),
    }


def _choice_value_ok(question: dict[str, Any], value: Any) -> bool:
    if value in question.get("options", []):
        return True
    # 允许"其他"时接受自由填写（前缀标识，防止伪造固定选项）
    return bool(question.get("allow_other")) and isinstance(value, str) and value.startswith(OTHER_PREFIX) and len(value) > len(OTHER_PREFIX)


def validate_answers(questions: list[dict[str, Any]], answers: dict[str, Any]) -> str | None:
    """按题目定义校验学生提交的答案，返回错误消息或 None。"""
    for question in questions:
        question_type = question.get("question_type")
        if question_type == "description":
            continue
        value = (answers.get(question.get("question_id")) or {}).get("answer")
        empty = (
            value is None
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, list) and not value)
        )
        label = question.get("question_text", "")
        if empty:
            if question.get("required"):
                return f"请回答：{label}"
            continue
        if question_type == "single_choice":
            if not _choice_value_ok(question, value):
                return f"「{label}」的答案不在选项中"
        elif question_type == "multiple_choice":
            if not isinstance(value, list) or any(
                not _choice_value_ok(question, item) for item in value
            ):
                return f"「{label}」的答案不在选项中"
        elif question_type == "number":
            try:
                number = float(value)
            except (TypeError, ValueError):
                return f"「{label}」需要填写数字"
            min_value = question.get("min_value")
            max_value = question.get("max_value")
            if min_value is not None and number < min_value:
                return f"「{label}」不能小于 {min_value:g}"
            if max_value is not None and number > max_value:
                return f"「{label}」不能大于 {max_value:g}"
        elif question_type == "date":
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError:
                return f"「{label}」需要填写日期"
        elif question_type == "rating":
            try:
                score = int(value)
            except (TypeError, ValueError):
                return f"「{label}」需要选择评分"
            if not 1 <= score <= int(question.get("max_rating") or 5):
                return f"「{label}」的评分超出范围"
        elif question_type in {"text", "textarea"}:
            text = str(value)
            max_length = int(question.get("max_length") or 500)
            if len(text) > max_length:
                return f"「{label}」超过最大字符数 {max_length}"
            text_format = question.get("format") or "none"
            if text_format in _FORMAT_PATTERNS:
                pattern, message = _FORMAT_PATTERNS[text_format]
                if not pattern.fullmatch(text.strip()):
                    return f"「{label}」{message}"
            elif text_format == "regex":
                try:
                    if not re.fullmatch(question.get("pattern") or "", text.strip()):
                        return f"「{label}」格式不符合要求"
                except re.error:
                    pass  # 模板保存时已校验过正则有效性
    return None


# ========== 现场签到 ==========


def generate_checkin_code(questionnaire_id: str) -> str:
    """生成该问卷内唯一的 6 位一次性签到码（每位报名者独立）。"""
    existing = {
        code
        for (code,) in db.session.query(QuestionnaireResponse.checkin_code)
        .filter_by(questionnaire_id=questionnaire_id)
        .all()
        if code
    }
    while True:
        code = f"{secrets.randbelow(900000) + 100000}"
        if code not in existing:
            return code


def assign_checkin_codes(template: ActivityQuestionnaire) -> int:
    """开启签到时为名额内（成功）且未签到的报名分配独立签到码；返回新分配的数量。

    候补默认不分配签到码，需要时由管理员逐人手动生成。
    """
    from backend.services.ranking import response_status

    assigned = 0
    responses = QuestionnaireResponse.query.filter_by(
        questionnaire_id=template.questionnaire_id, status="active"
    ).all()
    for response in responses:
        if response.checked_in_at or response.checkin_code:
            continue
        if response_status(response, template)["is_waitlist"]:
            continue
        response.checkin_code = generate_checkin_code(template.questionnaire_id)
        # 立即落库（事务内 flush），保证下一位的查重能看到刚分配的码
        db.session.flush()
        assigned += 1
    return assigned


def clear_checkin_codes(questionnaire_id: str) -> None:
    """关闭签到时作废该问卷的全部签到码。"""
    for response in QuestionnaireResponse.query.filter_by(
        questionnaire_id=questionnaire_id
    ).all():
        response.checkin_code = ""
