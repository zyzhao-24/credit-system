"""学生反馈：BUG 与活动漏录（含整个活动未录入的情况）。"""

from backend.extensions import db


class Feedback(db.Model):
    """一条反馈：学生提交，管理员回复并标记处理状态。

    type: bug=BUG 反馈（每人仅一条待处理，可修改）；missing=活动漏录。
    漏录申请带结构化字段（活动名/记录名/学分/类别 + 可选参与证据），
    match_hint 保存提交时与已有活动的朴素字符匹配结果，供管理员参考。
    管理员可核定修改后记录（adjustment）或拒绝（outcome=rejected）。
    status: pending=待处理；resolved=已结案（outcome 区分 recorded/rejected）。
    """

    __tablename__ = "feedbacks"
    __table_args__ = (
        db.CheckConstraint("type IN ('bug', 'missing')", name="ck_feedbacks_type"),
        db.CheckConstraint("status IN ('pending', 'resolved')", name="ck_feedbacks_status"),
    )

    feedback_id = db.Column(db.String(36), primary_key=True)
    # Deliberately no FK: feedback can outlive a student row.
    student_id = db.Column(db.String(32), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    # bug 反馈的正文（missing 类型为空串，内容见结构化字段）
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    reply = db.Column(db.Text, nullable=False, default="")
    handled_by = db.Column(db.String(100), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False)
    handled_at = db.Column(db.DateTime, nullable=True)

    # ---- 活动漏录的结构化字段 ----
    activity_name = db.Column(db.String(200), nullable=False, default="")
    record_name = db.Column(db.String(200), nullable=False, default="")
    credits = db.Column(db.Float, nullable=False, default=0)
    categories = db.Column(db.JSON, nullable=True)
    # 可选的参与证据（文字描述/链接等）
    evidence = db.Column(db.Text, nullable=False, default="")
    # 提交时的朴素字符匹配结果：[{"activity_id","name","rate"}]，仅作人工参考
    match_hint = db.Column(db.JSON, nullable=True)
    # 结案方式：""=未结案 / recorded=管理员核定并记录 / rejected=已拒绝
    outcome = db.Column(db.String(20), nullable=False, default="")
    # 管理员核定后的合理值：{"activity_name","record_name","credits","categories"}
    adjustment = db.Column(db.JSON, nullable=True)
