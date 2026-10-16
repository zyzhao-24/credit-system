"""Export the relational database in the legacy data.json shape."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    RegistrationQuestionnaire,
    Setting,
    Student,
)
from backend.services.legacy_import import DATETIME_FORMAT


def _number(value: Any) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else number


def _dt(value: datetime | None) -> str:
    return value.strftime(DATETIME_FORMAT) if value else ""


def export_legacy_payload(redact_sensitive: bool = True) -> dict[str, Any]:
    """Return a deterministic legacy-shaped dictionary.

    Passwords are redacted by default. With redact_sensitive=False they are
    exported as password hashes, never as recovered plaintext.
    """
    students = {
        student.student_id: {
            "name": student.name,
            "password": "<redacted>" if redact_sensitive else student.password_hash,
            "password_reset_required": student.password_reset_required,
        }
        for student in Student.query.order_by(Student.student_id.asc()).all()
    }
    admins = {
        admin.admin_id: {
            "password": "<redacted>" if redact_sensitive else admin.password_hash,
            "role": admin.role,
            "department": admin.department,
        }
        for admin in Admin.query.order_by(Admin.admin_id.asc()).all()
    }
    categories = {
        category.name: {"required_credits": _number(category.required_credits)}
        for category in Category.query.order_by(Category.position.asc()).all()
    }
    departments = [
        department.name
        for department in Department.query.order_by(Department.position.asc()).all()
    ]

    total_setting = db.session.get(Setting, "total_required_credits")
    email_config = db.session.get(EmailConfig, 1)

    activities: dict[str, Any] = {}
    for activity in Activity.query.order_by(Activity.position.asc()).all():
        records = []
        for record in sorted(activity.records, key=lambda item: item.position):
            records.append(
                {
                    "record_id": record.record_id,
                    "record_name": record.record_name,
                    "entries": [
                        {
                            "student_id": entry.student_id,
                            "credits": _number(entry.credits),
                            "categories": entry.categories,
                        }
                        for entry in sorted(record.entries, key=lambda item: item.position)
                    ],
                }
            )
        activities[activity.activity_id] = {
            "name": activity.name,
            "categories": activity.categories,
            "department": activity.department,
            "created_by": activity.created_by or "",
            "allowed_editors": activity.allowed_editors,
            "has_questionnaire": activity.has_questionnaire,
            "questionnaire_start": _dt(activity.questionnaire_start),
            "questionnaire_end": _dt(activity.questionnaire_end),
            "max_participants": activity.max_participants,
            "records": records,
        }

    registration_questionnaires = {
        item.questionnaire_id: {
            "student_id": item.student_id,
            "name": item.name,
            "phone": item.phone,
            "wechat": item.wechat,
            "suggestion": item.suggestion,
            "submit_time": _dt(item.submit_time),
        }
        for item in RegistrationQuestionnaire.query.order_by(
            RegistrationQuestionnaire.questionnaire_id.asc()
        ).all()
    }
    activity_questionnaires = {
        item.questionnaire_id: {
            "activity_id": item.activity_id,
            "title": item.title,
            "start_time": _dt(item.start_time),
            "end_time": _dt(item.end_time),
            "max_participants": item.max_participants,
            "has_category_question": item.has_category_question,
            "custom_questions": item.custom_questions,
            "created_time": _dt(item.created_time),
            "status": item.status,
        }
        for item in ActivityQuestionnaire.query.order_by(
            ActivityQuestionnaire.questionnaire_id.asc()
        ).all()
    }
    questionnaire_responses = {
        item.response_id: {
            "questionnaire_id": item.questionnaire_id,
            "student_id": item.student_id,
            "student_name": item.student_name,
            "phone": item.phone,
            "wechat": item.wechat,
            "intended_category": item.intended_category,
            "custom_answers": item.custom_answers,
            "submit_time": _dt(item.submit_time),
            "status": item.status,
        }
        for item in QuestionnaireResponse.query.order_by(
            QuestionnaireResponse.questionnaire_id.asc()
        ).all()
    }

    return {
        "students": students,
        "admins": admins,
        "categories": categories,
        "departments": departments,
        "total_required_credits": _number(total_setting.value) if total_setting else 0,
        "email_config": {
            "service_email": email_config.service_email if email_config else "",
            "service_email_password": "<redacted>",
            "student_email_suffix": email_config.student_email_suffix if email_config else "",
        },
        "activities": activities,
        "registration_questionnaires": registration_questionnaires,
        "activity_questionnaires": activity_questionnaires,
        "questionnaire_responses": questionnaire_responses,
    }
