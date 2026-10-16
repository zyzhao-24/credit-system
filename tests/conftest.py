"""Shared pytest fixtures for the refactored backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend import create_app
from backend.extensions import db as _db
from backend.services.legacy_import import import_legacy_payload


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.db"
    app = create_app(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path.as_posix()}",
        CORS_ORIGINS=[],
    )
    with app.app_context():
        _db.create_all()
    yield app
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture()
def database(app):
    with app.app_context():
        yield _db
        _db.session.remove()


@pytest.fixture()
def seed_legacy_payload(app, database):
    def seed(payload: dict) -> dict[str, int]:
        with app.app_context():
            counts = import_legacy_payload(payload)
            database.session.commit()
            return counts

    return seed


@pytest.fixture()
def minimal_payload():
    fixture = ROOT / "tests" / "fixtures" / "minimal_legacy.json"
    return json.loads(fixture.read_text(encoding="utf-8"))
