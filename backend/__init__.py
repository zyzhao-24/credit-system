"""Application factory for the refactored backend."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine

from backend.config import Config, ProductionConfig
from backend.extensions import db, migrate

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """Enable SQLite features needed by the single-process deployment."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def _ensure_schema(app: Flask) -> None:
    """Idempotent SQLite schema upgrades for databases created by older versions.

    The project manages schema via create_all rather than Alembic revision
    files, so new columns on existing tables are added here with plain
    ALTER TABLE guarded by PRAGMA table_info. Tables that were folded into
    other models (registration questionnaires are now student columns) are
    dropped here; their old data is discarded by design.
    """
    with app.app_context():
        db.create_all()
        if not db.engine.url.get_backend_name() == "sqlite":
            return
        additions = {
            "students": [
                "totp_secret_encrypted TEXT NOT NULL DEFAULT ''",
                "phone VARCHAR(20) NOT NULL DEFAULT ''",
                "wechat VARCHAR(100) NOT NULL DEFAULT ''",
                "suggestion TEXT NOT NULL DEFAULT ''",
                "info_updated_at DATETIME",
            ],
            "admins": ["totp_secret_encrypted TEXT NOT NULL DEFAULT ''"],
            # 提交时保存问卷快照 + 版本号，模板修改不影响历史提交
            "questionnaire_responses": [
                "template_snapshot JSON",
                "template_version INTEGER",
                # 现场签到：签到时间、候补签到确认、缺席标记、每人一次性签到码
                "checked_in_at DATETIME",
                "checkin_confirmed BOOLEAN NOT NULL DEFAULT 0",
                "absent BOOLEAN NOT NULL DEFAULT 0",
                "checkin_code VARCHAR(16) NOT NULL DEFAULT ''",
            ],
            "activity_questionnaires": [
                "version INTEGER NOT NULL DEFAULT 1",
                # 问卷绑定记录（类别题由记录类别自动生成）
                "record_id VARCHAR(36) NOT NULL DEFAULT ''",
                # 正文文档（题目嵌入文字流），旧数据为 NULL 按题目顺序合成
                "body JSON",
                # 现场签到会话：签到码与开关
                "checkin_open BOOLEAN NOT NULL DEFAULT 0",
                "checkin_code VARCHAR(16) NOT NULL DEFAULT ''",
            ],
            # 活动漏录反馈的结构化字段与结案信息
            "feedbacks": [
                "activity_name VARCHAR(200) NOT NULL DEFAULT ''",
                "record_name VARCHAR(200) NOT NULL DEFAULT ''",
                "credits FLOAT NOT NULL DEFAULT 0",
                "categories JSON",
                "evidence TEXT NOT NULL DEFAULT ''",
                "match_hint JSON",
                "outcome VARCHAR(20) NOT NULL DEFAULT ''",
                "adjustment JSON",
            ],
        }
        with db.engine.begin() as connection:
            for table, columns in additions.items():
                existing = {
                    row[1]
                    for row in connection.exec_driver_sql(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                }
                for column_def in columns:
                    name = column_def.split()[0]
                    if name not in existing:
                        connection.exec_driver_sql(
                            f"ALTER TABLE {table} ADD COLUMN {column_def}"
                        )
            # 注册问卷已并入 students 表，旧表连同数据一并删除
            connection.exec_driver_sql("DROP TABLE IF EXISTS registration_questionnaires")
            # 学分类别已从活动级下沉到记录级：把旧 activity_categories 的归属
            # 复制到该活动下的每条记录（保持原有顺序），然后删除旧表
            tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "activity_categories" in tables:
                connection.exec_driver_sql(
                    """
                    INSERT INTO record_categories (record_id, category_name, position)
                    SELECT r.record_id, ac.category_name, ac.position
                    FROM records r
                    JOIN activity_categories ac ON ac.activity_id = r.activity_id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM record_categories rc WHERE rc.record_id = r.record_id
                    )
                    """
                )
                connection.exec_driver_sql("DROP TABLE activity_categories")
            # 独立问卷（activity_id=''）不受"同一活动一个进行中问卷"限制：
            # 重建部分唯一索引以排除空 activity_id（幂等，可重复执行）
            connection.exec_driver_sql("DROP INDEX IF EXISTS uq_activity_questionnaires_one_active")
            connection.exec_driver_sql(
                """
                CREATE UNIQUE INDEX uq_activity_questionnaires_one_active
                ON activity_questionnaires (activity_id)
                WHERE status = 'active' AND activity_id != ''
                """
            )


def _ensure_system_admin(app: Flask) -> None:
    """内置 system 管理员固定存在（id 恒为 'system'）。

    首次启动时以随机且**不落盘、不打印**的密码建号——该密码无人知晓，
    初始配置通过本机专用维护页完成：启动服务后在服务器本机访问
    http://localhost:5000/local/system 设置密码并绑定 OTP。
    此后本函数不再触碰密码与 OTP。
    """
    import secrets

    from backend.models.core import Admin
    from backend.utils.passwords import client_password_digest, hash_password_digest

    with app.app_context():
        admin = db.session.get(Admin, "system")
        if admin is None:
            db.session.add(
                Admin(
                    admin_id="system",
                    password_hash=hash_password_digest(
                        client_password_digest(secrets.token_urlsafe(32))
                    ),
                    role="system_admin",
                    department="",
                )
            )
            db.session.commit()
            hint = (
                "已创建内置 system 管理员；初始密码与 OTP 请在服务器本机访问 "
                "http://localhost:5000/local/system 设置"
            )
            print(hint, flush=True)
            app.logger.warning(hint)
        elif admin.role != "system_admin":
            admin.role = "system_admin"
            db.session.commit()


def create_app(config_object: type[Config] | None = None, **overrides) -> Flask:
    env_name = os.getenv("FLASK_ENV", "development")
    if config_object is None:
        config_object = ProductionConfig if env_name == "production" else Config

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object())
    app.config.update(overrides)
    app.json.ensure_ascii = False

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models before migrations or create_all.
    from backend import models  # noqa: F401
    from backend.api.auth import auth_bp
    from backend.api.admin_activities import admin_activities_bp
    from backend.api.admin_settings import admin_settings_bp
    from backend.api.admin_students import admin_students_bp
    from backend.api.admin_questionnaires import admin_questionnaires_bp
    from backend.api.admin_reports import admin_reports_bp
    from backend.api.feedback import feedback_bp
    from backend.api.local_admin import local_admin_bp
    from backend.api.questionnaires import questionnaires_bp
    from backend.api.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_activities_bp)
    app.register_blueprint(admin_settings_bp)
    app.register_blueprint(admin_students_bp)
    app.register_blueprint(admin_questionnaires_bp)
    app.register_blueprint(admin_reports_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(local_admin_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(student_bp)

    _ensure_schema(app)
    _ensure_system_admin(app)

    cors_origins = app.config.get("CORS_ORIGINS", [])
    if cors_origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": cors_origins}},
            methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
            supports_credentials=False,
        )

    @app.get("/api/health")
    def health():
        return jsonify({"success": True, "status": "ok"})

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path: str):
        """Serve the React build; unknown non-API paths fall back to index.html."""
        if path.startswith("api/") or path == "api":
            return jsonify({"success": False, "message": "接口不存在"}), 404
        if not FRONTEND_DIST.is_dir():
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "前端尚未构建，请在 frontend/ 目录运行 npm run build",
                    }
                ),
                503,
            )
        if path:
            candidate = FRONTEND_DIST / path
            if candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
                return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")

    @app.after_request
    def cache_hashed_assets(response):
        """Vite 产物文件名带内容哈希，/assets/ 下的文件可以安全长缓存。"""
        if request.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    return app
