"""Application factory for the refactored backend."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine

from backend.config import Config, ProductionConfig
from backend.extensions import db, migrate


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """Enable SQLite features needed by the single-process deployment."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


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

    return app
