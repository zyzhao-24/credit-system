"""Student account helpers shared by auth and admin APIs."""

from __future__ import annotations

import re

from backend.extensions import db
from backend.models import QuestionnaireResponse, Student
from backend.utils.passwords import client_password_digest, hash_password_digest


PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


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
    return student


def delete_student_account(student: Student) -> int:
    """Delete a student and their questionnaire responses.

    Credit entries deliberately remain because the legacy system allows entries
    for missing student IDs and treats them as historical data. Contact info
    lives on the student row itself, so it disappears with the row.
    """
    deleted = QuestionnaireResponse.query.filter_by(student_id=student.student_id).delete()
    db.session.delete(student)
    return deleted
