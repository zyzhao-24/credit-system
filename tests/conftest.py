"""Shared pytest fixtures for the refactored backend."""

from __future__ import annotations

import json
from pathlib import Path

import pyotp
import pytest

from backend import create_app
from backend.extensions import db as _db
from backend.services.legacy_import import import_legacy_payload
from backend.utils.passwords import client_password_digest

from mailstub import SENT_MAIL, stub_send_email

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def stub_outbound_mail(monkeypatch):
    """Never send real email in tests; capture messages instead."""
    SENT_MAIL.clear()
    monkeypatch.setattr("backend.services.emailer.send_email", stub_send_email)
    monkeypatch.setattr("backend.api.auth.send_email", stub_send_email)
    monkeypatch.setattr("backend.services.otp_service.send_email", stub_send_email)
    yield


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.db"
    app = create_app(
        TESTING=True,
        SECRET_KEY="test-secret-key-with-at-least-32-bytes",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path.as_posix()}",
        CORS_ORIGINS=[],
        # 常规测试高频登录同一批账号，放宽防爆破限速以免误伤；
        # 限速本身由 test_auth.py 里使用 raw_app 的专项用例覆盖
        LOGIN_FAIL_MAX_PER_MINUTE=1000,
        LOGIN_FAIL_MAX_PER_HOUR=100000,
        OTP_FAIL_MAX_PER_TICKET=1000,
        OTP_FAIL_MAX_PER_MINUTE=10000,
    )
    with app.app_context():
        _db.create_all()
    yield app
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture()
def raw_app(tmp_path):
    """不带任何限速放行的 app，用于验证默认限速阈值本身。"""
    database_path = tmp_path / "test-raw.db"
    app = create_app(
        TESTING=True,
        SECRET_KEY="test-secret-key-with-at-least-32-bytes",
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
            # create_app 保证了内置 system 账号存在；导入夹带同 ID 账号时先移除
            from backend.models import Admin

            for admin_id in payload.get("admins", {}):
                existing = _db.session.get(Admin, admin_id)
                if existing is not None:
                    _db.session.delete(existing)
                _db.session.flush()
            counts = import_legacy_payload(payload)
            database.session.commit()
            return counts

    return seed


@pytest.fixture()
def minimal_payload():
    fixture = ROOT / "tests" / "fixtures" / "minimal_legacy.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


@pytest.fixture()
def login(app, database):
    """Complete the two-step login (password + TOTP) and return a Bearer header.

    Students/admins without a bound OTP get one auto-provisioned by the first
    step (students via the stubbed binding email; admins must be pre-bound).
    """
    from backend.models import Admin, Student
    from backend.services.otp_service import bind_new_totp, get_totp_secret

    def do_login(username: str, password: str, user_type: str) -> str:
        client = app.test_client()

        # Admins without OTP are rejected at step 1, so pre-bind them directly
        # in the database (equivalent to the OTP-bind API, no email involved).
        if user_type == "admin":
            with app.app_context():
                admin = _db.session.get(Admin, username)
                assert admin is not None, f"管理员不存在: {username}"
                if not get_totp_secret(admin):
                    bind_new_totp(admin)
                    _db.session.commit()

        step1 = client.post(
            "/api/auth/token",
            data={
                "grant_type": "password",
                "username": username,
                "password": client_password_digest(password),
                "user_type": user_type,
            },
        )
        assert step1.status_code == 200, step1.get_json()
        payload = step1.get_json()
        # 账号处于 OTP 信任期（一周内验证过）时第一步直接发令牌
        if not payload.get("otp_required"):
            assert payload.get("access_token"), payload
            return f"Bearer {payload['access_token']}"

        with app.app_context():
            model = Student if user_type == "student" else Admin
            account = _db.session.get(model, username)
            assert account is not None, f"账号不存在: {user_type}/{username}"
            secret = get_totp_secret(account)
            assert secret, "第一步登录后应已绑定 OTP"

        step2 = client.post(
            "/api/auth/token/verify",
            json={"otp_ticket": payload["otp_ticket"], "otp_code": pyotp.TOTP(secret).now()},
        )
        assert step2.status_code == 200, step2.get_json()
        assert step2.get_json()["success"] is True
        return f"Bearer {step2.get_json()['access_token']}"

    return do_login
