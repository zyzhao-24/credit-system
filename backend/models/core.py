"""Core account and system-setting models."""

from backend.extensions import db


class Student(db.Model):
    __tablename__ = "students"

    student_id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    password_reset_required = db.Column(db.Boolean, nullable=False, default=False)
    # 令牌版本：改密/重置/登出时 +1，使此前签发的 JWT 全部失效
    token_version = db.Column(db.Integer, nullable=False, default=0)
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
    password_reset_required = db.Column(db.Boolean, nullable=False, default=False)
    token_version = db.Column(db.Integer, nullable=False, default=0)
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


class TrustedDevice(db.Model):
    """OTP 信任记录：账号在某 IP / 某设备浏览器成功验证 OTP 后，一周内免 OTP。

    每次 OTP 验证成功写入一行：token_hash 是发给浏览器的设备 Cookie 的哈希，
    ip 是当时的来源 IP；登录第一步满足任一匹配（同设备或同 IP）且未过期即跳过 OTP。
    """

    __tablename__ = "trusted_devices"
    __table_args__ = (
        db.Index("ix_trusted_devices_account", "user_type", "account_id"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_type = db.Column(db.String(10), nullable=False)  # student / admin
    account_id = db.Column(db.String(100), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, index=True)
    ip = db.Column(db.String(45), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
