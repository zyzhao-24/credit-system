"""Localhost-only system account console tests."""

import re

from backend.models import Admin
from backend.services.otp_service import has_totp
from backend.utils.passwords import client_password_digest, verify_password_digest

TOKEN_PATTERN = re.compile(r'form_token" value="([^"]+)"')


def _form_token(client) -> str:
    page = client.get("/local/system")
    assert page.status_code == 200
    match = TOKEN_PATTERN.search(page.get_data(as_text=True))
    assert match is not None
    return match.group(1)


def test_console_hidden_from_remote_clients(app, database):
    remote = {"REMOTE_ADDR": "8.8.8.8"}
    assert app.test_client().get("/local/system", environ_overrides=remote).status_code == 404
    assert (
        app.test_client().post("/local/system/reset-password", environ_overrides=remote).status_code
        == 404
    )


def test_console_requires_signed_form_token(app, database):
    client = app.test_client()
    forged = client.post("/local/system/reset-password", data={"form_token": "bogus"})
    assert forged.status_code == 403
    missing = client.post("/local/system/reset-otp")
    assert missing.status_code == 403


def test_console_reset_password_and_otp(app, database):
    client = app.test_client()
    # create_app 保证 system 账号存在
    admin = database.session.get(Admin, "system")
    assert admin is not None

    token = _form_token(client)
    reset = client.post("/local/system/reset-password", data={"form_token": token})
    assert reset.status_code == 200
    match = re.search(r"<code style=\"font-size:18px\">([^<]+)</code>", reset.get_data(as_text=True))
    assert match is not None
    new_password = match.group(1)
    database.session.refresh(admin)
    assert verify_password_digest(admin.password_hash, client_password_digest(new_password))

    token = _form_token(client)
    otp = client.post("/local/system/reset-otp", data={"form_token": token})
    assert otp.status_code == 200
    html = otp.get_data(as_text=True)
    assert "data:image/png;base64," in html
    database.session.refresh(admin)
    assert has_totp(admin)
