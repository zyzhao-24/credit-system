"""Feedback API: students report bugs and missing credit records; admins reply.

BUG 反馈（常驻）：每人只维护一条待处理帖子（可修改）。
活动漏录（仅集中活动反馈开启期间可提交）：结构化申请（活动名/学分/类别 +
可选记录名与参与证据）——活动存在时选择记录（类别限该记录可行类别）或
不选记录（自选类别）；活动不存在时手动填写活动名、不填记录。提交时按朴素
字符匹配率比对已有活动作为提示，管理员核定修改后记录、或拒绝。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from backend.auth.decorators import require_admin, require_student
from backend.extensions import db
from backend.models import Activity, Category, Entry, Feedback, Record, Setting, Student
from backend.services.permissions import check_activity_edit_permission
from backend.services.ranking import format_datetime


feedback_bp = Blueprint("feedback", __name__)

FEEDBACK_TYPES = {"bug": "BUG 反馈", "missing": "活动漏录"}
MAX_CONTENT_LENGTH = 2000
MAX_REPLY_LENGTH = 2000
OUTCOMES = {"recorded": "已记录", "rejected": "已拒绝"}
_MATCH_MIN_RATE = 0.2
_MATCH_TOP_N = 3
# 集中活动反馈开关（Setting 表）：开启期间学生才能提交活动漏录申请；BUG 反馈常驻
MISSING_OPEN_KEY = "missing_feedback_open"


def _missing_feedback_open() -> bool:
    setting = db.session.get(Setting, MISSING_OPEN_KEY)
    return bool(setting and setting.value == "1")


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _char_match_rate(a: str, b: str) -> float:
    """朴素字符匹配率：去空白后字符集合的 Jaccard 相似度（仅作人工参考）。"""
    clean_a = set(re.sub(r"\s", "", a))
    clean_b = set(re.sub(r"\s", "", b))
    if not clean_a or not clean_b:
        return 0.0
    return len(clean_a & clean_b) / len(clean_a | clean_b)


def _match_activities(activity_name: str) -> list[dict]:
    """与全部已有活动名做朴素字符匹配，返回重合率最高的前几个。"""
    matches = []
    for activity in Activity.query.all():
        rate = _char_match_rate(activity_name, activity.name)
        if rate >= _MATCH_MIN_RATE:
            matches.append(
                {
                    "activity_id": activity.activity_id,
                    "name": activity.name,
                    "rate": round(rate, 2),
                }
            )
    matches.sort(key=lambda item: item["rate"], reverse=True)
    return matches[:_MATCH_TOP_N]


def _payload(item: Feedback) -> dict:
    return {
        "feedback_id": item.feedback_id,
        "student_id": item.student_id,
        "student_name": item.student_name,
        "type": item.type,
        "type_text": FEEDBACK_TYPES.get(item.type, item.type),
        "content": item.content,
        "status": item.status,
        "outcome": item.outcome,
        "outcome_text": OUTCOMES.get(item.outcome, ""),
        "reply": item.reply,
        "handled_by": item.handled_by,
        "created_at": format_datetime(item.created_at),
        "handled_at": format_datetime(item.handled_at),
        # 漏录结构化字段
        "activity_name": item.activity_name,
        "record_name": item.record_name,
        "credits": item.credits,
        "categories": item.categories or [],
        "evidence": item.evidence,
        "match_hint": item.match_hint or [],
        # entry_id 是取消核定时的内部簿记，不下发
        "adjustment": (
            {key: value for key, value in item.adjustment.items() if key != "entry_id"}
            if item.adjustment
            else None
        ),
    }


# ========== 学生端 ==========


@feedback_bp.post("/api/student/feedback")
@require_student
def submit_feedback():
    """提交反馈。BUG：每人仅一条待处理（已有时请改为修改）；漏录：结构化字段。"""
    student_id = g.current_identity.get("sub")
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("学生不存在，请联系管理员")

    data = request.get_json(silent=True) or {}
    feedback_type = data.get("type", "").strip()
    if feedback_type not in FEEDBACK_TYPES:
        return _error("请选择反馈类型")

    feedback = Feedback(
        feedback_id=str(uuid.uuid4()),
        student_id=student.student_id,
        student_name=student.name,
        type=feedback_type,
        content="",
        status="pending",
        created_at=datetime.now(),
    )

    if feedback_type == "bug":
        content = data.get("content", "").strip()
        if not content:
            return _error("请填写反馈内容")
        if len(content) > MAX_CONTENT_LENGTH:
            return _error(f"内容超过最大长度 {MAX_CONTENT_LENGTH} 字")
        existing = Feedback.query.filter_by(
            student_id=student.student_id, type="bug", status="pending"
        ).first()
        if existing is not None:
            return _error("您已有一条待处理的 BUG 反馈，请直接修改原反馈")
        feedback.content = content
    else:
        # 活动漏录：仅集中活动反馈开启期间可提交（BUG 反馈常驻）。
        # 活动存在：选择记录（类别限该记录可行类别）或不选记录（自选类别）；
        # 活动不存在：手动填写活动名，此时记录不需要也不能填，自选类别。
        if not _missing_feedback_open():
            return _error("当前未开启集中活动反馈，暂不能提交活动漏录申请")
        activity_name = data.get("activity_name", "").strip()
        record_name = data.get("record_name", "").strip()
        if not activity_name:
            return _error("请选择或填写活动名称")
        try:
            credits = float(data.get("credits", 0))
        except (TypeError, ValueError):
            return _error("学分量必须是数字")
        if credits <= 0:
            return _error("学分量必须大于 0")
        categories = data.get("categories", [])
        if not isinstance(categories, list):
            return _error("请选择至少一个类别")
        category_names = [
            str(category).strip() for category in categories if str(category).strip()
        ]
        if not category_names:
            return _error("请选择至少一个类别")
        valid_names = {category.name for category in Category.query.all()}
        unknown = [name for name in category_names if name not in valid_names]
        if unknown:
            return _error(f"类别不存在：{'、'.join(unknown)}")
        feedback.activity_name = activity_name
        feedback.record_name = record_name
        feedback.credits = credits
        feedback.categories = category_names
        activity = Activity.query.filter_by(name=activity_name).first()
        if activity is None:
            if record_name:
                return _error("活动不在系统中时无需填写记录名称")
        elif record_name:
            record = next((r for r in activity.records if r.record_name == record_name), None)
            if record is None:
                return _error("该活动下没有此记录，请从已有记录中选择，或不选择记录")
            invalid = [name for name in feedback.categories if name not in record.categories]
            if invalid:
                feasible = "、".join(record.categories) or "（无）"
                return _error(
                    f"记录「{record_name}」的可行类别为：{feasible}，"
                    f"类别 {'、'.join(invalid)} 不在其中"
                )
        feedback.evidence = data.get("evidence", "").strip()[:MAX_CONTENT_LENGTH]
        feedback.match_hint = _match_activities(activity_name)

    db.session.add(feedback)
    db.session.commit()
    return jsonify({"success": True, "message": "反馈已提交，管理员会尽快处理"})


@feedback_bp.put("/api/student/feedback/<feedback_id>")
@require_student
def edit_feedback(feedback_id: str):
    """修改自己的待处理 BUG 反馈（漏录申请提交后不可改，由管理员核定）。"""
    item = db.session.get(Feedback, feedback_id)
    if item is None or item.student_id != g.current_identity.get("sub"):
        return _error("反馈不存在")
    if item.type != "bug":
        return _error("漏录申请提交后不可修改")
    if item.status != "pending":
        return _error("已处理的反馈不可修改")
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return _error("请填写反馈内容")
    if len(content) > MAX_CONTENT_LENGTH:
        return _error(f"内容超过最大长度 {MAX_CONTENT_LENGTH} 字")
    item.content = content
    db.session.commit()
    return jsonify({"success": True, "message": "修改成功"})


@feedback_bp.post("/api/student/feedback/match")
@require_student
def match_activities():
    """输入活动名，返回与已有活动的朴素字符匹配结果（填写时的重合提示）。"""
    data = request.get_json(silent=True) or {}
    activity_name = data.get("activity_name", "").strip()
    if not activity_name:
        return jsonify({"success": True, "matches": []})
    return jsonify({"success": True, "matches": _match_activities(activity_name)})


@feedback_bp.get("/api/student/feedback/activities")
@require_student
def feedback_activity_options():
    """漏录申请的选项数据：全部活动及各自记录的可行类别。"""
    activities = Activity.query.order_by(Activity.position.asc()).all()
    return jsonify(
        {
            "success": True,
            "activities": [
                {
                    "activity_id": activity.activity_id,
                    "name": activity.name,
                    "records": [
                        {
                            "record_id": record.record_id,
                            "record_name": record.record_name,
                            "categories": record.categories,
                        }
                        for record in activity.records
                    ],
                }
                for activity in activities
            ],
        }
    )


@feedback_bp.get("/api/student/feedback")
@require_student
def my_feedback():
    """我的反馈列表（最新在前），含处理状态、核定结果与回复。"""
    student_id = g.current_identity.get("sub")
    items = (
        Feedback.query.filter_by(student_id=student_id)
        .order_by(Feedback.created_at.desc())
        .all()
    )
    return jsonify(
        {
            "success": True,
            "feedbacks": [_payload(item) for item in items],
            "missing_open": _missing_feedback_open(),
        }
    )


# ========== 管理端 ==========


@feedback_bp.get("/api/admin/feedback")
@require_admin
def admin_feedback_list():
    """反馈列表：待处理优先，其余按时间倒序。所有管理员可见可处理。"""
    items = Feedback.query.all()
    # 待处理按提交时间正序（先报先处理），已处理按时间倒序
    pending = sorted((i for i in items if i.status == "pending"), key=lambda i: i.created_at)
    resolved = sorted(
        (i for i in items if i.status != "pending"), key=lambda i: i.created_at, reverse=True
    )
    ordered = pending + resolved
    return jsonify(
        {
            "success": True,
            "feedbacks": [_payload(item) for item in ordered],
            "missing_open": _missing_feedback_open(),
        }
    )


@feedback_bp.post("/api/admin/feedback/missing_open")
@require_admin
def set_missing_feedback_open():
    """开启/关闭集中活动反馈。开启期间学生才能提交活动漏录申请；BUG 反馈常驻。"""
    data = request.get_json(silent=True) or {}
    open_now = data.get("open")
    if not isinstance(open_now, bool):
        return _error("open 必须是布尔值")
    setting = db.session.get(Setting, MISSING_OPEN_KEY)
    if setting is None:
        setting = Setting(key=MISSING_OPEN_KEY)
        db.session.add(setting)
    setting.value = "1" if open_now else "0"
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "missing_open": open_now,
            "message": "已开启集中活动反馈" if open_now else "已关闭集中活动反馈",
        }
    )


@feedback_bp.post("/api/admin/feedback/<feedback_id>/handle")
@require_admin
def handle_feedback(feedback_id: str):
    """处理反馈。action:
    - reply：回复 BUG 反馈并结案（reply 必填）
    - record：漏录申请核定并记录（adjustment 必填 + reply 必填）。
      活动/记录不存在时自动创建；已有记录时核定类别必须属于该记录的
      可行类别；完全相同的已有条目不重复录入；
      自动录入的条目 ID 存入 adjustment，取消核定时自动删除。
    - reject：拒绝漏录申请（reply 必填）
    - reopen：重新打开（回到待处理，清空结案方式；已记录的自动删除对应条目）
    """
    item = db.session.get(Feedback, feedback_id)
    if item is None:
        return _error("反馈不存在")
    data = request.get_json(silent=True) or {}
    action = data.get("action", "").strip()
    reply = data.get("reply", "").strip()
    if len(reply) > MAX_REPLY_LENGTH:
        return _error(f"回复超过最大长度 {MAX_REPLY_LENGTH} 字")

    if action == "reopen":
        note, error = _delete_recorded_entry(item, g.current_identity)
        if error:
            return _error(error)
        item.status = "pending"
        item.outcome = ""
        item.adjustment = None
        item.reply = ""
        item.handled_by = ""
        item.handled_at = None
        db.session.commit()
        return jsonify({"success": True, "message": f"已重新打开{note}"})

    if item.status != "pending":
        return _error("该反馈已处理，如需变更请先重新打开")
    if not reply:
        return _error("请先填写回复内容")

    if action == "reply":
        if item.type != "bug":
            return _error("漏录申请请选择记录或拒绝")
        outcome = ""
        adjustment = None
        message = "已处理"
    elif action == "record":
        if item.type != "missing":
            return _error("BUG 反馈请直接回复")
        # 管理员核定后的合理值：活动名/记录名/学分/类别（可与学生申请不同）
        adjusted = data.get("adjustment", {}) or {}
        activity_name = str(adjusted.get("activity_name", "")).strip()
        record_name = str(adjusted.get("record_name", "")).strip()
        if not activity_name or not record_name:
            return _error("请核定活动名称和记录名称")
        try:
            credits = float(adjusted.get("credits", 0))
        except (TypeError, ValueError):
            return _error("核定学分必须是数字")
        if credits <= 0:
            return _error("核定学分必须大于 0")
        categories = adjusted.get("categories", [])
        if not isinstance(categories, list):
            return _error("请核定至少一个类别")
        category_names = [
            str(category).strip() for category in categories if str(category).strip()
        ]
        if not category_names:
            return _error("请核定至少一个类别")
        valid_names = {category.name for category in Category.query.all()}
        unknown = [name for name in category_names if name not in valid_names]
        if unknown:
            return _error(f"类别不存在：{'、'.join(unknown)}")

        entry_id, notes, error = _record_adjusted_entry(
            item, g.current_identity, activity_name, record_name, credits, category_names
        )
        if error:
            return _error(error)
        outcome = "recorded"
        adjustment = {
            "activity_name": activity_name,
            "record_name": record_name,
            "credits": credits,
            "categories": category_names,
            # 自动录入的条目 ID：取消核定时据此删除对应条目
            "entry_id": entry_id,
        }
        message = "已核定并记录" + ("；" + "；".join(notes) if notes else "")
    elif action == "reject":
        if item.type != "missing":
            return _error("BUG 反馈请直接回复")
        outcome = "rejected"
        adjustment = None
        message = "已处理"
    else:
        return _error("无效的处理方式")

    item.reply = reply
    item.status = "resolved"
    item.outcome = outcome
    item.adjustment = adjustment
    item.handled_by = g.current_identity.get("sub", "")
    item.handled_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True, "message": message})


def _record_adjusted_entry(
    item: Feedback,
    identity: dict,
    activity_name: str,
    record_name: str,
    credits: float,
    category_names: list[str],
) -> tuple[int | None, list[str], str | None]:
    """按核定结果录入条目。返回 (entry_id, 操作说明列表, 错误消息)。

    - 活动不存在：自动创建（创建者为处理人，处理人获得编辑权限）
    - 记录不存在：在该活动下自动创建，类别取核定类别
    - 记录已存在：核定类别必须属于该记录的可行类别，否则报错
    - 完全相同的条目（同学号、同学分、同类别集合）已存在：不重复录入
    """
    notes: list[str] = []
    activity = Activity.query.filter_by(name=activity_name).first()
    if activity is None:
        position = db.session.query(func.max(Activity.position)).scalar() or 0
        activity = Activity(
            activity_id=str(uuid.uuid4()),
            name=activity_name,
            department=identity.get("department", ""),
            created_by=identity.get("sub"),
            position=position + 1,
        )
        activity.allowed_editors = [identity.get("sub")]
        db.session.add(activity)
        db.session.flush()
        notes.append(f"已自动创建活动「{activity_name}」")
    elif not check_activity_edit_permission(identity, activity.activity_id):
        return None, notes, f"您没有活动「{activity_name}」的编辑权限，无法记录到该活动"

    record = next((r for r in activity.records if r.record_name == record_name), None)
    if record is None:
        record = Record(
            record_id=str(uuid.uuid4()),
            record_name=record_name,
            position=len(activity.records),
        )
        record.categories = category_names
        activity.records.append(record)
        db.session.flush()
        notes.append(f"已自动创建记录「{record_name}」")
    else:
        invalid = [name for name in category_names if name not in record.categories]
        if invalid:
            feasible = "、".join(record.categories) or "（无）"
            return None, notes, (
                f"记录「{record_name}」的可行类别为：{feasible}，"
                f"类别 {'、'.join(invalid)} 不在其中"
            )

    duplicate = next(
        (
            entry
            for entry in record.entries
            if entry.student_id == item.student_id
            and entry.credits == credits
            and set(entry.categories) == set(category_names)
        ),
        None,
    )
    if duplicate is not None:
        notes.append("相同条目已存在，未重复录入")
        return None, notes, None

    entry = Entry(
        record_id=record.record_id,
        student_id=item.student_id,
        credits=credits,
        position=len(record.entries),
    )
    entry.categories = category_names
    record.entries.append(entry)
    db.session.flush()
    return entry.entry_id, notes, None


def _delete_recorded_entry(item: Feedback, identity: dict) -> tuple[str, str | None]:
    """取消核定时删除当时自动录入的对应条目（不影响活动与记录本身）。

    返回 (结果说明, 错误消息)。删除条目与录入一样要求活动编辑权限；
    条目被管理员改动过（学分/类别与核定值不符）时不删，交由人工处理。
    """
    if item.outcome != "recorded" or not isinstance(item.adjustment, dict):
        return "", None
    entry_id = item.adjustment.get("entry_id")
    if entry_id is None:
        return "", None
    entry = db.session.get(Entry, int(entry_id))
    if entry is None:
        return "，对应条目已不存在", None
    activity = entry.record.activity
    if not check_activity_edit_permission(identity, activity.activity_id):
        return "", f"您没有活动「{activity.name}」的编辑权限，无法取消该核定"
    unchanged = (
        entry.student_id == item.student_id
        and entry.credits == item.adjustment.get("credits")
        and set(entry.categories) == set(item.adjustment.get("categories", []))
    )
    if not unchanged:
        return "，对应条目已被修改，请人工核对后处理", None
    db.session.delete(entry)
    return "，对应条目已删除", None
