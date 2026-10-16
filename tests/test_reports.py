"""Report and workbook export tests."""

import io

import openpyxl

from backend.utils.passwords import client_password_digest


def token(client, username, password, user_type):
    response = client.post(
        "/api/auth/token",
        data={"username": username, "password": client_password_digest(password), "user_type": user_type},
    )
    return f"Bearer {response.get_json()['access_token']}"


def test_query_report_and_excel_export(app, database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    system = token(client, "system", "adminpass", "admin")
    normal = token(client, "admin", "adminpass", "admin")

    queried = client.post("/api/query/student", json={"query": "测试学生一"}, headers={"Authorization": system})
    assert queried.status_code == 200
    assert queried.get_json()["student_id"] == "1001"
    assert queried.get_json()["total_credits"] == 3

    system_report = client.get("/api/admin/report", headers={"Authorization": system}).get_json()
    normal_report = client.get("/api/admin/report", headers={"Authorization": normal}).get_json()
    assert system_report["total_students"] == 2
    assert "students" in system_report
    assert "students" not in normal_report

    exported = client.get("/api/admin/export", headers={"Authorization": system})
    assert exported.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(exported.get_data()))
    worksheet = workbook.active
    assert worksheet["A1"].value == "学号"
    assert worksheet["E1"].value == "思想品德学分"
    assert worksheet.max_row == 3
