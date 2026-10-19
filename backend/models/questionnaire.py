"""Questionnaire template and response models.

报名信息（手机号/微信号/建议）已并入 students 表（见 models/core.py），
这里只保留活动问卷模板与报名响应。
"""

from backend.extensions import db


class ActivityQuestionnaire(db.Model):
    """问卷模板：activity_id 非空为活动报名问卷，空字符串为独立问卷（不绑定活动）。"""

    __tablename__ = "activity_questionnaires"
    __table_args__ = (
        # 同一活动只允许一个进行中的报名问卷；独立问卷（activity_id=''）不受此限
        db.Index(
            "uq_activity_questionnaires_one_active",
            "activity_id",
            unique=True,
            sqlite_where=db.text("status = 'active' AND activity_id != ''"),
        ),
        db.CheckConstraint("status IN ('active', 'closed')", name="ck_activity_questionnaires_status"),
    )

    questionnaire_id = db.Column(db.String(36), primary_key=True)
    # Deliberately no FK: legacy behavior leaves templates behind when an activity is deleted.
    # Empty string means a standalone questionnaire not bound to any activity.
    activity_id = db.Column(db.String(36), nullable=False, default="", index=True)
    # 绑定的记录（须属于 activity_id 对应的活动）；空字符串表示未绑定。
    # 意向类别题由记录类别自动生成：多类别→单选题（缺省为"无"），单一类别→自动归入。
    record_id = db.Column(db.String(36), nullable=False, default="", index=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_participants = db.Column(db.Integer, nullable=False, default=0)
    has_category_question = db.Column(db.Boolean, nullable=False, default=True)
    custom_questions = db.Column(db.JSON, nullable=False, default=list)
    # 正文文档：段落数组，每段为 {"type":"text","text":...} 与
    # {"type":"question","question_id":...} 片段的有序混排；题目嵌入文字流中。
    # 旧数据为 NULL，读取时按题目顺序合成（见 services.questionnaires.synthesize_body）
    body = db.Column(db.JSON, nullable=True)
    # 模板版本：题目或标题每次修改时 +1，提交记录绑定提交时的版本
    version = db.Column(db.Integer, nullable=False, default=1)
    # 现场签到：管理员开启后每位报名者分配独立的一次性签到码（见响应表），关闭后清空
    checkin_open = db.Column(db.Boolean, nullable=False, default=False)
    # 已废弃：早期版本的全问卷共享签到码，现为每人一码，此列仅留作历史兼容
    checkin_code = db.Column(db.String(16), nullable=False, default="")
    created_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")

    @property
    def is_standalone(self) -> bool:
        return not self.activity_id


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
    # 提交时的问卷快照（标题/类别题开关/自定义题目），问卷模板后续修改不影响历史提交
    template_snapshot = db.Column(db.JSON, nullable=True)
    # 提交时模板的版本号（旧数据为 NULL）
    template_version = db.Column(db.Integer, nullable=True)
    submit_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    # 现场签到：候补签到为"待确认"（checkin_confirmed=False），管理员确认或
    # 候补因缺席转正后自动生效；缺席标记使该报名不再占用名额
    checked_in_at = db.Column(db.DateTime, nullable=True)
    checkin_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    absent = db.Column(db.Boolean, nullable=False, default=False)
    # 每人独立的一次性签到码：开启签到时分配，签到成功或关闭签到后清空
    checkin_code = db.Column(db.String(16), nullable=False, default="")

    questionnaire = db.relationship("ActivityQuestionnaire")
