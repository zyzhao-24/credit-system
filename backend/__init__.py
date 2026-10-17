"""Application factory for the refactored backend."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
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
    """Idempotent SQLite schema upgrades for databases created before OTP.

    The project manages schema via create_all rather than Alembic revision
    files, so new columns on existing tables are added here with plain
    ALTER TABLE guarded by PRAGMA table_info.
    """
    with app.app_context():
        db.create_all()
        if not db.engine.url.get_backend_name() == "sqlite":
            return
        additions = {
            "students": ["totp_secret_encrypted TEXT NOT NULL DEFAULT ''"],
            "admins": ["totp_secret_encrypted TEXT NOT NULL DEFAULT ''"],
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


def _ensure_system_admin(app: Flask) -> None:
    """The built-in system admin account always exists (fixed id 'system')."""
    from backend.models.core import Admin
    from backend.utils.passwords import client_password_digest, hash_password_digest

    with app.app_context():
        admin = db.session.get(Admin, "system")
        if admin is None:
            db.session.add(
                Admin(
                    admin_id="system",
                    password_hash=hash_password_digest(client_password_digest("sysadmin")),
                    role="system_admin",
                    department="",
                )
            )
            db.session.commit()
            app.logger.warning("已创建内置 system 管理员（初始密码 sysadmin，请用 manage.py 修改）")
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
    from backend.api.questionnaires import questionnaires_bp
    from backend.api.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_activities_bp)
    app.register_blueprint(admin_settings_bp)
    app.register_blueprint(admin_students_bp)
    app.register_blueprint(admin_questionnaires_bp)
    app.register_blueprint(admin_reports_bp)
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

    return app
