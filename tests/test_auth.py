"""Authentication API tests."""

from backend.models import RegistrationQuestionnaire, Student
from backend.utils.passwords import client_password_digest


def test_oauth2_password_token_and_me(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()

    response = client.post(
        "/api/auth/token",
        data={
            "grant_type": "password",
            "username": "1001",
            "password": client_password_digest("pass123"),
            "user_type": "student",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["token_type"] == "bearer"
    assert payload["user_type"] == "student"
    assert payload["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["sub"] == "1001"

    student = database.session.get(Student, "1001")
    assert student.password_hash != "pass123"
    assert student.password_hash.startswith("pbkdf2:sha256:")


def test_admin_token_and_legacy_login(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()

    response = client.post(
        "/api/auth/token",
        data={
            "username": "system",
            "password": client_password_digest("adminpass"),
            "user_type": "admin",
        },
    )
    assert response.status_code == 200
    token = response.get_json()["access_token"]
    info = client.get(
        "/api/admin/session_info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert info.status_code == 200
    assert info.get_json()["role"] == "system_admin"

    legacy = client.post(
        "/api/login/admin",
        json={"username": "admin", "password_hash": client_password_digest("adminpass")},
    )
    assert legacy.status_code == 200
    assert legacy.get_json()["success"] is True
    assert legacy.get_json()["role"] == "admin"


def test_wrong_password_is_rejected(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    response = app.test_client().post(
        "/api/auth/token",
        data={
            "username": "1001",
            "password": client_password_digest("wrong-password"),
            "user_type": "student",
        },
    )
    assert response.status_code == 401


def test_registration_creates_questionnaire_and_hashes_password(app, database):
    client = app.test_client()
    response = client.post(
        "/api/student/register",
        json={
            "name": "新学生",
            "student_id": "2001",
            "phone": "13700000000",
            "wechat": "new-wechat",
            "password": "secret123",
            "suggestion": "建议",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    student = database.session.get(Student, "2001")
    questionnaire = RegistrationQuestionnaire.query.filter_by(student_id="2001").one()
    assert student.password_hash.startswith("pbkdf2:sha256:")
    assert questionnaire.wechat == "new-wechat"
