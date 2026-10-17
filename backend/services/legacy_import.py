"""Import the legacy JSON document into the relational schema.

This module is shared by the migration script and tests. It preserves list and
object insertion order explicitly because several legacy behaviors depend on it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import current_app

from backend.extensions import db
from backend.models import (
    Activity,
    ActivityQuestionnaire,
    Admin,
    Category,
    Department,
    EmailConfig,
    Entry,
    QuestionnaireResponse,
    Record,
    Setting,
    Student,
)
from backend.utils.crypto import encrypt_secret
from backend.utils.passwords import client_password_digest, hash_password_digest


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
FORM_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (DATETIME_FORMAT, FORM_DATETIME_FORMAT):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"不支持的时间格式: {value!r}")


def import_legacy_payload(payload: dict[str, Any]) -> dict[str, int]:
    """Insert a legacy data.json payload into the current SQLAlchemy session."""
    for position, (student_id, item) in enumerate(payload.get("students", {}).items()):
        db.session.add(
            Student(
                student_id=student_id,
                name=item["name"],
                password_hash=hash_password_digest(client_password_digest(item["password"])),
                password_reset_required=item.get("password_reset_required", False),
            )
        )

    for admin_id, item in payload.get("admins", {}).items():
        db.session.add(
            Admin(
                admin_id=admin_id,
                password_hash=hash_password_digest(client_password_digest(item["password"])),
                role=item.get("role", "admin"),
                department=item.get("department", ""),
            )
        )

    # Ensure referenced admins exist before activities are inserted.
    db.session.flush()

    for position, (name, item) in enumerate(payload.get("categories", {}).items()):
        db.session.add(
            Category(
                name=name,
                required_credits=float(item["required_credits"]),
                position=position,
            )
        )

    # Category names are referenced by activity and entry association rows.
    db.session.flush()

    for position, name in enumerate(payload.get("departments", [])):
        db.session.add(Department(name=name, position=position))

    db.session.add(
        Setting(
            key="total_required_credits",
            value=str(payload.get("total_required_credits", 0)),
        )
    )

    email_config = payload.get("email_config", {})
    db.session.add(
        EmailConfig(
            id=1,
            service_email=email_config.get("service_email", ""),
            service_email_password_encrypted=encrypt_secret(
                email_config.get("service_email_password", ""),
                current_app.config["SECRET_KEY"],
            ),
            student_email_suffix=email_config.get("student_email_suffix", ""),
        )
    )

    activities = payload.get("activities", {})
    for activity_position, (activity_id, item) in enumerate(activities.items()):
        activity = Activity(
            activity_id=activity_id,
            name=item["name"],
            department=item.get("department", ""),
            created_by=item.get("created_by") or None,
            has_questionnaire=item.get("has_questionnaire", False),
            questionnaire_start=parse_datetime(item.get("questionnaire_start")),
            questionnaire_end=parse_datetime(item.get("questionnaire_end")),
            max_participants=item.get("max_participants", 0),
            position=activity_position,
        )
        activity.categories = item.get("categories", [])
        activity.allowed_editors = item.get("allowed_editors", [])
        db.session.add(activity)

        for record_position, record_item in enumerate(item.get("records", [])):
            record = Record(
                record_id=record_item["record_id"],
                record_name=record_item["record_name"],
                position=record_position,
            )
            activity.records.append(record)
            for entry_position, entry_item in enumerate(record_item.get("entries", [])):
                entry = Entry(
                    student_id=entry_item["student_id"],
                    credits=float(entry_item["credits"]),
                    position=entry_position,
                )
                entry.categories = entry_item.get("categories", [])
                record.entries.append(entry)

    # 注册问卷已并入 students 表：联系方式直接写到对应学生行，学号缺失的记录丢弃
    mapped_infos = 0
    for item in payload.get("registration_questionnaires", {}).values():
        student = db.session.get(Student, item["student_id"])
        if student is None:
            continue
        student.phone = item.get("phone", "")
        student.wechat = item.get("wechat", "")
        student.suggestion = item.get("suggestion", "")
        student.info_updated_at = parse_datetime(item.get("submit_time"))
        mapped_infos += 1

    for questionnaire_id, item in payload.get("activity_questionnaires", {}).items():
        db.session.add(
            ActivityQuestionnaire(
                questionnaire_id=questionnaire_id,
                activity_id=item["activity_id"],
                title=item["title"],
                start_time=parse_datetime(item["start_time"]),
                end_time=parse_datetime(item["end_time"]),
                max_participants=item.get("max_participants", 0),
                has_category_question=item.get("has_category_question", True),
                custom_questions=item.get("custom_questions", []),
                created_time=parse_datetime(item.get("created_time")),
                status=item.get("status", "active"),
            )
        )

    for response_id, item in payload.get("questionnaire_responses", {}).items():
        db.session.add(
            QuestionnaireResponse(
                response_id=response_id,
                questionnaire_id=item["questionnaire_id"],
                student_id=item["student_id"],
                student_name=item["student_name"],
                phone=item.get("phone", ""),
                wechat=item.get("wechat", ""),
                intended_category=item.get("intended_category", ""),
                custom_answers=item.get("custom_answers", {}),
                submit_time=parse_datetime(item["submit_time"]),
                status=item.get("status", "active"),
            )
        )

    return {
        "students": len(payload.get("students", {})),
        "admins": len(payload.get("admins", {})),
        "categories": len(payload.get("categories", {})),
        "departments": len(payload.get("departments", [])),
        "activities": len(activities),
        "records": sum(len(item.get("records", [])) for item in activities.values()),
        "entries": sum(
            len(record.get("entries", []))
            for item in activities.values()
            for record in item.get("records", [])
        ),
        "registration_questionnaires": len(payload.get("registration_questionnaires", {})),
        "activity_questionnaires": len(payload.get("activity_questionnaires", {})),
        "questionnaire_responses": len(payload.get("questionnaire_responses", {})),
    }
