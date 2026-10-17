"""Core account and system-setting models."""

from backend.extensions import db


class Student(db.Model):
    __tablename__ = "students"

    student_id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    password_reset_required = db.Column(db.Boolean, nullable=False, default=False)
    totp_secret_encrypted = db.Column(db.Text, nullable=False, default="")
    # 报名信息是学生档案的一部分，不再是独立问卷
    phone = db.Column(db.String(20), nullable=False, default="")
    wechat = db.Column(db.String(100), nullable=False, default="")
    suggestion = db.Column(db.Text, nullable=False, default="")
    info_updated_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.CheckConstraint("length(student_id) > 0", name="ck_students_id_not_empty"),
    )


class Admin(db.Model):
    __tablename__ = "admins"

    admin_id = db.Column(db.String(100), primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="admin")
    department = db.Column(db.String(100), nullable=False, default="")
    totp_secret_encrypted = db.Column(db.Text, nullable=False, default="")

    __table_args__ = (
        db.CheckConstraint("role IN ('admin', 'system_admin')", name="ck_admins_role"),
    )


class Category(db.Model):
    __tablename__ = "categories"

    name = db.Column(db.String(100), primary_key=True)
    required_credits = db.Column(db.Float, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    position = db.Column(db.Integer, nullable=False, default=0)


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")


class EmailConfig(db.Model):
    __tablename__ = "email_config"

    id = db.Column(db.Integer, primary_key=True)
    service_email = db.Column(db.String(255), nullable=False, default="")
    service_email_password_encrypted = db.Column(db.Text, nullable=False, default="")
    student_email_suffix = db.Column(db.String(255), nullable=False, default="")

    __table_args__ = (
        db.CheckConstraint("id = 1", name="ck_email_config_singleton"),
    )


class EmailVerification(db.Model):
    """Registration email verification codes (hashed, time-limited)."""

    __tablename__ = "email_verifications"

    student_id = db.Column(db.String(32), primary_key=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False)
