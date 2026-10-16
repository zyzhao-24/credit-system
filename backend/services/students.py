"""Student account helpers shared by auth and admin APIs."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from backend.extensions import db
from backend.models import QuestionnaireResponse, RegistrationQuestionnaire, Student
from backend.utils.passwords import client_password_digest, hash_password_digest


PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


def ensure_registration_questionnaire(student: Student) -> bool:
    """Ensure a student has exactly one registration questionnaire."""
    exists = RegistrationQuestionnaire.query.filter_by(student_id=student.student_id).first()
    if exists:
        return False
    db.session.add(
        RegistrationQuestionnaire(
            questionnaire_id=str(uuid.uuid4()),
            student_id=student.student_id,
            name=student.name,
            phone="",
            wechat="",
            suggestion="",
            submit_time=datetime.now(),
        )
    )
    return True


def ensure_all_registration_questionnaires() -> int:
    created = 0
    for student in Student.query.all():
        if ensure_registration_questionnaire(student):
            created += 1
    return created


def create_student(
    student_id: str,
    name: str,
    password: str,
    *,
    password_is_digest: bool = False,
) -> Student:
    digest = password if password_is_digest else client_password_digest(password)
    student = Student(
        student_id=student_id,
        name=name,
        password_hash=hash_password_digest(digest),
        password_reset_required=False,
    )
    db.session.add(student)
    db.session.flush()
    ensure_registration_questionnaire(student)
    return student


def delete_student_and_questionnaires(student: Student) -> int:
    """Delete a student and questionnaire records belonging to them.

    Credit entries deliberately remain because the legacy system allows entries
    for missing student IDs and treats them as historical data.
    """
    deleted = RegistrationQuestionnaire.query.filter_by(student_id=student.student_id).delete()
    deleted += QuestionnaireResponse.query.filter_by(student_id=student.student_id).delete()
    db.session.delete(student)
    return deleted
