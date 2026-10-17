"""Questionnaire template and response models.

报名信息（手机号/微信号/建议）已并入 students 表（见 models/core.py），
这里只保留活动问卷模板与报名响应。
"""

from backend.extensions import db


class ActivityQuestionnaire(db.Model):
    __tablename__ = "activity_questionnaires"
    __table_args__ = (
        db.Index(
            "uq_activity_questionnaires_one_active",
            "activity_id",
            unique=True,
            sqlite_where=db.text("status = 'active'"),
        ),
        db.CheckConstraint("status IN ('active', 'closed')", name="ck_activity_questionnaires_status"),
    )

    questionnaire_id = db.Column(db.String(36), primary_key=True)
    # Deliberately no FK: legacy behavior leaves templates behind when an activity is deleted.
    activity_id = db.Column(db.String(36), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_participants = db.Column(db.Integer, nullable=False, default=0)
    has_category_question = db.Column(db.Boolean, nullable=False, default=True)
    custom_questions = db.Column(db.JSON, nullable=False, default=list)
    created_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")


class QuestionnaireResponse(db.Model):
    __tablename__ = "questionnaire_responses"
    __table_args__ = (
        db.UniqueConstraint("questionnaire_id", "student_id", name="uq_response_once_per_student"),
        db.CheckConstraint("status IN ('active', 'cancelled')", name="ck_responses_status"),
    )

    response_pk = db.Column(db.Integer, primary_key=True, autoincrement=True)
    response_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    questionnaire_id = db.Column(
        db.String(36),
        db.ForeignKey("activity_questionnaires.questionnaire_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Deliberately no FK: responses are submission snapshots and can outlive a student row.
    student_id = db.Column(db.String(32), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, default="")
    wechat = db.Column(db.String(100), nullable=False, default="")
    intended_category = db.Column(db.String(100), nullable=False, default="")
    custom_answers = db.Column(db.JSON, nullable=False, default=dict)
    submit_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")

    questionnaire = db.relationship("ActivityQuestionnaire")
